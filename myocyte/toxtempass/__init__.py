class Config:
    """Put all parameters below here."""

    temperature = 0
    base_prompt="""/
    You are an agent tasked with answering the question below. Use only the provided context to formulate your response. 
    If the answer is not within the context, acknowledge that you don't know. Keep your response concise.
    /
    CONTEXT:/
    {context}/
    /
    QUESTION:/
    {question}
    """


config = Config()
