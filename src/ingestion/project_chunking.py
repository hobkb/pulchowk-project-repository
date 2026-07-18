import re

from .domain_classifier import classify_project_domain_full
from .task_classifier import classify_project_task_full


_STOPWORDS = {
    "the","a","an","of","and","or","in","on","to","for","with",
    "by","as","is","are","was","were","be","been","being",
    "this","that","these","those","it","its","from","at",
    "which","will","can","also","our","we",

    "project","report","study","research",
    "paper","thesis","chapter","figure","table",

    "abstract","introduction","background",
    "objective","objectives",

    "methodology","method",
    "approach",
    "technique","techniques",

    "results","conclusion","future",

    "using","used","based"
}


class ProjectLevelChunker:


    @staticmethod
    def clean_text(text):

        if not text:
            return ""

        text = re.sub(
            r"(\w+)-\s*\n\s*(\w+)",
            r"\1\2",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()



    @staticmethod
    def extract_keywords(text, top_n=15):

        if not text.strip():
            return []


        from sklearn.feature_extraction.text import TfidfVectorizer


        try:

            vectorizer = TfidfVectorizer(
                ngram_range=(1,2),
                stop_words=list(_STOPWORDS)
            )


            matrix = vectorizer.fit_transform(
                [text]
            )


            scores = matrix.toarray()[0]


            terms = vectorizer.get_feature_names_out()


            ranked = sorted(
                zip(terms, scores),
                key=lambda x:x[1],
                reverse=True
            )


            return [
                term
                for term,_ in ranked[:top_n]
            ]


        except ValueError:

            return []



    @staticmethod
    def extract_signal_text(text,max_words):

        if not text:
            return "Not found"


        sentences=re.split(
            r"[.!?]",
            text
        )


        useful=[]


        for sentence in sentences:

            sentence=sentence.strip()

            words=sentence.lower().split()


            if len(words)<=5:
                continue


            noise=sum(
                1
                for word in words
                if word in _STOPWORDS
            )


            if noise < len(words)/2:

                useful.append(sentence)



        result=" ".join(useful)


        return " ".join(
            result.split()[:max_words]
        ) or "Not found"



    @classmethod
    def build_project_profile(
        cls,
        project_title,
        content_chunks,
        top_n_keywords=15
    ):


        abstracts=[]
        objectives=[]
        methods=[]



        for chunk in content_chunks:


            metadata = chunk.get(
                "metadata",
                {}
            )


            text = chunk.get(
                "text",
                ""
            )


            if not text:
                continue



            page_type = metadata.get(
                "page_type",
                ""
            )


            section = metadata.get(
                "section_title",
                ""
            ).lower()



            if (
                page_type=="abstract"
                or
                "abstract" in section
            ):

                abstracts.append(text)



            elif any(
                key in section
                for key in [
                    "objective",
                    "aim",
                    "goal"
                ]
            ):

                objectives.append(text)



            elif any(
                key in section
                for key in [
                    "method",
                    "architecture",
                    "framework",
                    "implementation"
                ]
            ):

                methods.append(text)




        abstract = cls.clean_text(
            " ".join(abstracts)
        )


        objective = cls.clean_text(
            "".join(objectives)
        )


        methodology = cls.clean_text(
            " ".join(methods)
        )



        # fallback only if extraction failed

        if not abstract:

            abstract = cls.extract_signal_text(
                " ".join(
                    chunk.get("text","")
                    for chunk in content_chunks
                ),
                100
            )


        if not objective:

            objective = cls.extract_signal_text(
                abstract,
                50
            )


        if not methodology:

            methodology = cls.extract_signal_text(
                abstract,
                100
            )



        combined=f"""
{project_title}
{abstract}
{objective}
{methodology}
"""



        # Domain / task classification now goes through the shared weighted
        # ontology engine (domain_classifier / task_classifier), which
        # supports multi-word phrases and negative-vote disambiguation --
        # not the old single-word rule dicts. classify_*_full also returns
        # every category that scored above zero, ranked descending, so a
        # project doesn't get forced into a single bucket when it
        # legitimately spans more than one domain (e.g. a wearable ECG
        # project is both "Healthcare & Biomedical AI" and
        # "Internet of Things & Embedded Systems").

        domain, domain_ranked = classify_project_domain_full(combined)

        task, task_ranked = classify_project_task_full(combined)


        domain_scores = [
            {"domain": name, "score": round(score, 2)}
            for name, score in domain_ranked
        ]


        task_scores = [
            {"task": name, "score": round(score, 2)}
            for name, score in task_ranked
        ]


        # Secondary domains/tasks (everything after the top pick) get
        # folded into the embedding text so semantic search can still
        # surface a project under a related domain even when it isn't the
        # single strongest one.

        secondary_domains = [name for name, _ in domain_ranked[1:]]

        secondary_tasks = [name for name, _ in task_ranked[1:]]


        keywords=cls.extract_keywords(
            combined,
            top_n_keywords
        )



        embedding_text=f"""
PROJECT DOMAIN:
{domain}

SECONDARY DOMAINS:
{", ".join(secondary_domains) if secondary_domains else "None"}

AI TASK:
{task}

SECONDARY TASKS:
{", ".join(secondary_tasks) if secondary_tasks else "None"}

PROJECT TITLE:
{project_title}

IMPORTANT TECHNICAL CONCEPTS:
{", ".join(keywords)}

PROJECT DESCRIPTION:
{cls.extract_signal_text(abstract,35)}

PROBLEM SOLVED:
{cls.extract_signal_text(objective,25)}

TECHNICAL APPROACH:
{cls.extract_signal_text(methodology,35)}

RELATED CONCEPTS:
{domain},
{task},
artificial intelligence,
machine learning,
deep learning,
neural networks
""".strip()



        return {

            "project_title":project_title,

            "domain":domain,

            "task":task,

            "domain_scores":domain_scores,

            "task_scores":task_scores,

            "abstract":abstract,

            "objectives":objective,

            "methodology":methodology,

            "keywords":keywords,

            "embedding_text":embedding_text

        }
