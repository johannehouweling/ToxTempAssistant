# ToxTempAssistantApp
LLM-added population of ToxTemp for test method description. [1]

- [ToxTempAssistantApp](#toxtempassistantapp)
  - [Install](#install)
  - [TODO](#todo)
    - [Functionality](#functionality)
    - [Production changes](#production-changes)
    - [Performance optimization](#performance-optimization)
    - [Infrastructure](#infrastructure)
  - [License](#license)
  - [Maintainer](#maintainer)
  - [References](#references)

## Install
- luaLaTeX (Mactex)
## TODO
### Functionality
- Fix document references. Implement RAG after all?
- Filtering: User
- Collaboration option? Easier option to show User study only to users
- Disclaimer on Privacy etc.
- Write tests
- Add possibility to use images (untested code):
  ```python
  import os
  import requests

  # Replace with the correct model name
  MODEL_NAME = "gpt-4-vision"

  # Path to your local image
  IMAGE_PATH = "./img1.png"

  # System message indicating vision capabilities
  system_message = {
      "role": "system",
      "content": """
      You are ChatPal, an AI assistant powered by GPT-4 with computer vision.
      AI knowledge cutoff: October 2023

      Built-in vision capabilities:
      - extract text from image
      - describe images
      - analyze image contents
      - logical problem solving requiring reasoning and contextual consideration
      """.strip()
  }

  # User message requesting image analysis
  user_message = {
      "role": "user",
      "content": "Analyze this image, using built-in vision."
  }

  # Prepare the payload
  payload = {
      "model": MODEL_NAME,
      "messages": [system_message, user_message],
      "max_tokens": 1500,
      "top_p": 0.5,
      "temperature": 0.5,
  }

  # Prepare the files payload
  files = {
      "file": (
          os.path.basename(IMAGE_PATH),
          open(IMAGE_PATH, "rb"),
          "image/png"  # Adjust MIME type based on your image format
      )
  }

  # Headers with authorization
  headers = {
      "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"
  }

  # Make the POST request
  response = requests.post(
      "https://api.openai.com/v1/chat/completions",
      headers=headers,
      data={'payload': json.dumps(payload)},  # Some APIs require JSON payload as a string
      files=files
  )

  # Check the response
  if response.status_code == 200:
      print("Response:", response.json())
  else:
      print(f"Error {response.status_code}: {response.text}")
  ```
- Add keywords in export files, ontologies?
- take care of deleting generated files after download by user
- likelihood score responses
### Production changes
- get `orcid_client_id` and `orcid_client_secret` for production
  - Login to ORCDI then click on user-settings -> Developper Tools 
  - >Developer tools
    >Back to my record
    >Client ID
    >APP-0H3CSLELBDG6NSWO
    >Client secret
    >b00fc3ed-3ec0-4ce4-a7a7-d88ea4fac163
    >Generate a new client secret
    >Application details
    >Application name
    >ToxTempAssistant
    >The name shown to users on the OAuth authorization screen
    >Application URL
    >http://127.0.0.1:8000
    >Application description
    >ToxTempAssistance helps researchers fill out the ToxTemp by leveraging large languge models. 
    >
    >ToxTemp, "an annotated toxicity test method template was developed (i) to fulfill all requirements of GD211, (ii) to guide the user concerning the types of answers and detail of information required, (iii) >to include acceptance criteria for test elements, and (iv) to define the cells sufficiently and transparently." (dx.doi.org/10.14573/altex.1909271)
    >The description shown to users on the OAuth authorization screen. Maximum 1000 characters.
    >Redirect URIs
    >Once the user has authorized your application, they will be returned to a URI that you specify. You must provide these URIs in advance or your integration users will experience an error.
    >
    >Please note
    >Only HTTPS URIs are accepted in production
    >Domains registered MUST exactly match the domains used, including subdomains
    >Register all redirect URIs fully where possible. This is the most secure option and what we recommend. For more information about redirect URIs, please see our redirect URI FAQ
    >http://127.0.0.1:8000/orcid/callback/



### Performance optimization
-  History: Make sure we Cache the Answers on first shipment of the Answer.html, so that if we store answers we don't have to hit the database again.
-  Handle concurrency / prevent multiple users from checking/editing the same item (only need if we allow colaboration) 
### Infrastructure
- Check for context window, are we not cutting it off if someone upload uploads oomany files
- Implement RAG to refer to most relevant chunks
- VHP4Safety GPT endpoint. Set limit to number of draft generations.
- Where will this app be hosted? 
- Dockerize in and host on AzureDocker?
- What is stored? At the moment answers and document-names and username ISA.
## License

## Maintainer
- Johanne Houweling | firstname.lastname@rivm.nl
- Matthias Arras | firstname.lastname@gmail.com
## References
[1]: Krebs, Alice, et al. "Template for the description of cell-based toxicological test methods to allow evaluation and regulatory use of the data." ALTEX-Alternatives to animal experimentation 36.4 (2019): 682-699.

