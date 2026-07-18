import re


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


_WORD_PATTERN = re.compile(
    r"\b[a-zA-Z0-9_-]{3,}\b"
)


# KEEP YOUR EXISTING DOMAIN RULES
# KEEP YOUR EXISTING TASK RULES

import re


_STOPWORDS = {
    ...
}


_WORD_PATTERN = re.compile(
    r"\b[a-zA-Z0-9_-]{3,}\b"
)


_DOMAIN_RULES = {

    "Computer Vision & Image Processing": {

        "face":10,
        "image":6,
        "video":6,
        "camera":6,
        "opencv":10,
        "yolo":10,
        "segmentation":10,
        "pixel":6,
        "vision":8,
        "object":5,
        "detection":4,
        "cnn":3,
        "gan":5,
    },


    "Natural Language Processing": {

        "text":7,
        "language":10,
        "sentence":10,
        "bert":10,
        "sbert":10,
        "transformer":8,
        "embedding":8,
        "semantic":8,
        "similarity":8,
        "question":7,
        "tokenization":10,
        "corpus":8,
        "llm":10,
    },


    "Biomedical AI & Signal Processing": {

        "ppg":15,
        "ecg":15,
        "eeg":15,
        "heart":10,
        "pulse":10,
        "blood":8,
        "oxygen":8,
        "medical":10,
        "clinical":10,
        "physiological":12,
        "signal":7,
    },


    "Healthcare AI": {

        "disease":10,
        "diagnosis":10,
        "doctor":8,
        "patient":8,
        "mri":12,
        "tumor":12,
        "healthcare":12,
    },


    "Hardware & IoT": {

        "arduino":15,
        "esp32":15,
        "sensor":8,
        "iot":12,
        "microcontroller":15,
        "raspberry":10,
        "embedded":10,
        "firmware":10,
    },


    "Web & Software Systems": {

        "django":10,
        "react":10,
        "frontend":8,
        "backend":8,
        "api":8,
        "database":8,
        "postgresql":10,
        "mongodb":8,
        "flutter":10,
    }

}



_TASK_RULES = {

    "Object Detection":{
        "yolo":10,
        "bounding":10,
        "detection":8,
        "localization":8,
    },


    "Recognition":{
        "recognition":10,
        "face":8,
        "identity":10,
    },


    "Prediction":{
        "prediction":10,
        "forecast":8,
        "estimate":8,
    },


    "Classification":{
        "classification":10,
        "categorization":8,
    },


    "Semantic Similarity":{
        "similarity":12,
        "sbert":12,
        "embedding":10,
        "sentence":8,
    },


    "Generation":{
        "generation":10,
        "generative":10,
        "music":8,
    },


    "Detection & Analysis":{
        "detection":8,
        "analysis":5
    }

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
    def infer_domain(text):

        words=set(
            _WORD_PATTERN.findall(
                text.lower()
            )
        )


        scores={}


        for domain,terms in _DOMAIN_RULES.items():

            scores[domain]=sum(
                weight
                for term,weight in terms.items()
                if term in words
            )


        best=max(
            scores,
            key=scores.get
        )


        if scores[best]==0:
            return "General Software Engineering"


        return best



    @staticmethod
    def infer_task(text):

        words=set(
            _WORD_PATTERN.findall(
                text.lower()
            )
        )


        scores={}


        for task,terms in _TASK_RULES.items():

            scores[task]=sum(
                weight
                for term,weight in terms.items()
                if term in words
            )


        best=max(
            scores,
            key=scores.get
        )


        if scores[best]==0:
            return "General Analysis"


        return best



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



        domain=cls.infer_domain(
            combined
        )


        task=cls.infer_task(
            combined
        )


        keywords=cls.extract_keywords(
            combined,
            top_n_keywords
        )



        embedding_text=f"""
PROJECT DOMAIN:
{domain}

AI TASK:
{task}

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

            "abstract":abstract,

            "objectives":objective,

            "methodology":methodology,

            "keywords":keywords,

            "embedding_text":embedding_text

        }