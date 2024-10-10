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
## TODO
### Functionality
- Filtering: User, Investigation->Study-Assay (only show assays per selected study etc)
- Collaboration option? Easier option to show User study only to users
- Disclaimer on Privacy etc.
- Output generation -> Json, XML, PDF
- Write tests
- Add functionality to allow GPT on per question/multi-question level.
- Somewhere log the documents that have been used for generation of draft answers.
- Mark answer as accepted
### Performance optimization
-  History: Make sure we Cache the Answers on first shipment of the Answer.html, so that if we store answers we don't have to hit the database again. 
## License

## Maintainer
- Johanne Houweling | firstname.lastname@rivm.nl
- Matthias Arras | firstname.lastname@gmail.com
## References
[1]: Krebs, Alice, et al. "Template for the description of cell-based toxicological test methods to allow evaluation and regulatory use of the data." ALTEX-Alternatives to animal experimentation 36.4 (2019): 682-699.
