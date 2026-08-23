"""
Canonical major-section heading aliases.

Shared between DocumentPageClassifier (which decides whether a page is a
"content" page at all) and MetadataSectionsStep (which turns headings on
content pages into section boundaries). Keeping a single table means a
report whose first chapter uses a heading style/wording this list doesn't
yet know about fails in one predictable place, instead of the two
classifiers silently disagreeing with each other.
"""

MAJOR_SECTION_ALIASES = {
    # Introduction and context
    'background': 'Background',
    'context': 'Background',
    'introduction': 'Introduction',
    'introduction and background': 'Introduction',
    'problem background': 'Background',
    'problem context': 'Background',
    'problem statement': 'Problem Statement',
    'research background': 'Background',

    # Problem, objectives, and scope
    'objectives': 'Objectives',
    'project objectives': 'Objectives',
    'research objectives': 'Objectives',
    'project scope': 'Scope',
    'scope and limitations': 'Scope',
    'scope of the study': 'Scope',
    'significance of the study': 'Significance',
    'statement of the problem': 'Problem Statement',

    # Literature and related work
    'literature review': 'Literature Review',
    'literature survey': 'Literature Review',
    'related literature': 'Literature Review',
    'related studies': 'Related Work',
    'related work': 'Related Work',
    'review of literature': 'Literature Review',
    'state of the art': 'Related Work',

    # Analysis, requirements, and design
    'requirement analysis': 'Requirements Analysis',
    'requirements analysis': 'Requirements Analysis',
    'requirements specification': 'Requirements',
    'system analysis': 'System Analysis',
    'system architecture': 'System Design',
    'system design': 'System Design',
    'system overview': 'System Design',
    'system specification': 'System Design',

    # Methodology and approach
    'approach': 'Methodology',
    'methodology': 'Methodology',
    'method': 'Methodology',
    'methodology and design': 'Methodology',
    'proposed approach': 'Methodology',
    'proposed methodology': 'Methodology',
    'research methodology': 'Methodology',
    'research design': 'Methodology',
    'technical approach': 'Methodology',

    # Proposed system and implementation
    'implementation': 'Implementation',
    'implementation details': 'Implementation',
    'implementation methodology': 'Implementation',
    'proposed system': 'Proposed System',
    'system implementation': 'Implementation',
    'system development': 'Implementation',

    # Experimental setup and evaluation
    'experimental setup': 'Experiments',
    'experimental methodology': 'Experiments',
    'experimental results': 'Results',
    'experiments': 'Experiments',
    'experiments and results': 'Results',
    'experiments and evaluation': 'Evaluation',
    'performance analysis': 'Evaluation',
    'performance evaluation': 'Evaluation',
    'proposed experimental setup': 'Experiments',

    'test results': 'Results',
    'validation': 'Validation',

    # Data and dataset
    'data collection': 'Data Collection',
    'data acquisition': 'Data Collection',
    'data sources': 'Data Collection',

    'dataset': 'Dataset',
    'dataset description': 'Dataset',
    'dataset overview': 'Dataset',
    'data description': 'Dataset',

    # Data exploration
    'data exploration': 'Data Exploration',
    'exploratory data analysis': 'Data Exploration',
    'exploratory analysis': 'Data Exploration',
    'data analysis': 'Data Exploration',

    # Data preprocessing
    'data preprocessing': 'Data Preprocessing',
    'data pre-processing': 'Data Preprocessing',
    'data preparation': 'Data Preprocessing',
    'data cleaning': 'Data Preprocessing',

    # Results and discussion
    'analysis and discussion': 'Discussion',
    'discussion': 'Discussion',
    'discussion and analysis': 'Discussion',
    'results and findings': 'Results',
    'findings': 'Results',
    'results': 'Results',
    'results and analysis': 'Results',
    'results and discussion': 'Results',
    'result and discussion': 'Results',
    'results and discussions': 'Results',
    'experimental results and findings': 'Results',
    'experimental results and discussion': 'Results',
    'experimental results and discussions': 'Results',
    'outcome': 'Results',
    'outcomes': 'Results',

    # Evaluation and comparison
    'comparison': 'Evaluation',
    'comparative analysis': 'Evaluation',
    'evaluation': 'Evaluation',
    'evaluation and analysis': 'Evaluation',
    'evaluation results': 'Evaluation',
    'performance comparison': 'Evaluation',
    'system evaluation': 'Evaluation',

    # Resources
    'resources': 'Resources',
    'resources used': 'Resources',
    'project resources': 'Resources',
    'project resource': 'Resources',
    'resource used': 'Resources',

    # Limitations and future work
    'future enhancement': 'Future Enhancement',
    'future enhancements': 'Future Enhancement',
    'future improvement': 'Future Enhancement',
    'future improvements': 'Future Enhancement',
    'future scope': 'Future Enhancement',
    'future work': 'Future Enhancement',
    'limitations': 'Limitations',
    'limitations and future enhancements': 'Future Enhancement',
    'limitations and future enhancement': 'Future Enhancement',
    'limitations and future work': 'Future Enhancement',

    'challenges faced': 'Challenges',
    'challenges': 'Challenges',

    # Conclusion and recommendations
    'conclusion': 'Conclusion',
    'conclusion and future work': 'Conclusion',
    'conclusions': 'Conclusion',
    'concluding remarks': 'Conclusion',
    'final remarks': 'Conclusion',
    'recommendation': 'Recommendations',
    'recommendations': 'Recommendations',
    'summary': 'Conclusion',
    'summary and conclusion': 'Conclusion',
    'summary and conclusions': 'Conclusion',
}


def normalize_major_heading(text: str) -> str:
    """Strip a leading 'Chapter N' or numeric 'N.N' prefix from a heading
    line, the same way both the page classifier and the section extractor
    need to before checking it against MAJOR_SECTION_ALIASES."""
    import re

    normalized = re.sub(r"^chapter\s+(?:[ivxlcdm]+|\d+)\b[\s.:\-]*", "", text, flags=re.IGNORECASE)
    normalized = re.sub(r"^\d+(?:\.\d+)*[.) :\-]+", "", normalized)
    return normalized.strip().rstrip(":")
