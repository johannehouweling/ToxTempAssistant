class Config:
    """Put all parameters below here."""

    model = "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"  # for gpt-4o mini
    # url = 'https://api.openai.com/v1/' #for gpt3.5
    temperature = 0
    base_prompt = """/
    You are an agent tasked with answering the question below. Use only the provided context to formulate your response. 
    If the answer is not within the context, acknowledge that you don't know. Keep your response concise.
    """


config = Config()
