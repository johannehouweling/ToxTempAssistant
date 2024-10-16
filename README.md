# ToxTempAssistantApp
PDF-based, LLM assisted assistiant to report your assay via the ToxTemplate. [1]

- [ToxTempAssistantApp](#toxtempassistantapp)
  - [Install](#install)
  - [TODO](#todo)
    - [Functionality](#functionality)
    - [Performance optimization](#performance-optimization)
  - [License](#license)
  - [Maintainer](#maintainer)
  - [References](#references)

## Install
- luaLaTeX (Mactex)
## TODO
### Functionality
- Filtering: User
- Collaboration option? Easier option to show User study only to users
- Disclaimer on Privacy etc.
- Write tests
- Add functionality to allow GPT on per question/multi-question level.
- Somewhere log the documents that have been used for generation of draft answers.
- Mark answer as accepted
- Add keywords in export files, ontologies?
- take care of deleting generated files after download by user
### Performance optimization
-  History: Make sure we Cache the Answers on first shipment of the Answer.html, so that if we store answers we don't have to hit the database again.
-  Handle concurrency / prevent multiple users from checking/editing the same item (only need if we allow colaboration) 
## License

## Maintainer
- Johanne Houweling | firstname.lastname@rivm.nl
- Matthias Arras | firstname.lastname@gmail.com
## References
[1]: Krebs, Alice, et al. "Template for the description of cell-based toxicological test methods to allow evaluation and regulatory use of the data." ALTEX-Alternatives to animal experimentation 36.4 (2019): 682-699.
