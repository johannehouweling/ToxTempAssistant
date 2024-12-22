# ToxTempAssistantApp
LLM-added population of ToxTemp for test method description. [1]

- [ToxTempAssistantApp](#toxtempassistantapp)
  - [Install](#install)
  - [TODO](#todo)
    - [Functionality](#functionality)
    - [Performance optimization](#performance-optimization)
    - [Infrastructure](#infrastructure)
  - [License](#license)
  - [Maintainer](#maintainer)
  - [References](#references)

## Install
- luaLaTeX (Mactex)
## TODO
### Functionality
- Filtering: User
- Login capability. Account management. Define user model
- Collaboration option? Easier option to show User study only to users
- Disclaimer on Privacy etc.
- Write tests
- Add keywords in export files, ontologies?
- take care of deleting generated files after download by user
- likelihood score responses
### Performance optimization
-  History: Make sure we Cache the Answers on first shipment of the Answer.html, so that if we store answers we don't have to hit the database again.
-  Handle concurrency / prevent multiple users from checking/editing the same item (only need if we allow colaboration) 
### Infrastructure
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
