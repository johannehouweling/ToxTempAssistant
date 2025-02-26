# ToxTempAssistantApp
LLM based web-app to assist users in drafting an annotated toxicity test method template (ToxTemp).

ToxTemp "was developed (i) to fulfill all requirements of GD211, (ii) to guide the user concerning the types of answers and detail of information required, (iii) >to include acceptance criteria for test elements, and (iv) to define the cells sufficiently and transparently." [1]

## TOC
- [ToxTempAssistantApp](#toxtempassistantapp)
  - [TOC](#toc)
  - [Spin up server with docker](#spin-up-server-with-docker)
    - [Get OpenAI API credentials](#get-openai-api-credentials)
    - [Get Orcid iD credentials](#get-orcid-id-credentials)
    - [Create Certificate](#create-certificate)
  - [License](#license)
  - [Maintainer](#maintainer)
  - [References](#references)

## Spin up server with docker
We work with a `.env` file to store mission critical information and setups. These need to be set to match your local environment. In addition, please revise `myocyte/dockerfiles/nginx/nginx.conf` to the settings needed for your specific setup.

Modify and rename the '.env.dummy'-file to `.env` in same path as the `docker-compose.yml` with configuration data on server

- `DEBUG` settitng for django should be False for production
- `SECRET_KEY` for django, salt for pw hashes
- `OPENAI_API_KEY` for LLM access
- `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRECT` to facilitate login via ORCID (see below for details)
- `ALLOWED_HOSTS` URI of the app, and IP address of server, potentaially also furhter aliases
- `POSTGRES_HOST` IP address of dedicated Postgres server if available, otherwise postgres_for_django to use postgres included in docker compose (obviously, the postgres server can be taken out of the docker compose if an external server is used)
- `POSTGRES_PORT` Port of Postgres Server, usually 5432, also use 5432 for docker compose postgres
- `POSTGRES_USER` Postgres User, default 'postgres'
- `POSTGRES_PASSWORD` Password for user, needs to be set using psql (see below)
- `POSTGRES_DB` Database name for django to use, also postgres user needs to be granted permissions to said db (see below)


The easier way to spin up the server is by using our docker compose file, if you are using an external PostGres Server, it is best to remove the postgres portion and its network from the docker-file. 
```bash
docker compose -f docker-compose.yml up
```

### Get OpenAI API credentials
https://platform.openai.com/api-keys

### Get Orcid iD credentials
To obtain orcid id and secret perform the following steps:
- login to personal or instutional orcid
- then click on user-settings -> Developper Tools 
- Confirm Terms of Servicen and click 'Register for your ORCID Public API credentials'
- Fill in Application Name, Application URL, Application Description and Redirect URIs
- Application Name: ToxTempAssistant
- Application URL: URL e.g. https://toxtempass.mainlvldomain.nl
- Application Description (suggestion): ToxTemp, "an annotated toxicity test method template was developed (i) to fulfill all requirements of GD211, (ii) to guide the user concerning the types of answers and detail of information required, (iii) >to include acceptance criteria for test elements, and (iv) to define the cells sufficiently and transparently." (dx.doi.org/10.14573/altex.1909271)
- Redirect URI: URL/orcid/callback/ e.g. https://toxtempass.mailvldomain.nl/orcid/callback/
   
### Create Certificate
Required for orcid login and general privacy considerations, it is advised to setup https. To this end a certificate is required. Create a Certificate Signing Request and send it to Certifying Authority, your institution should have someone. 
See this article, which also has some details on making the certificiate work with nginx: https://www.digitalocean.com/community/tutorials/how-to-create-a-self-signed-ssl-certificate-for-nginx-in-ubuntu-20-04-1


## License
This project is licensed under the GNU Affero General Public License, see the LICENSE file for details.

## Maintainer
- Jente Houweling | firstname.lastname@rivm.nl
- Matthias Arras | firstname.lastname@gmail.com
  
## References
[1]: Krebs, Alice, et al. "Template for the description of cell-based toxicological test methods to allow evaluation and regulatory use of the data." ALTEX-Alternatives to animal experimentation 36.4 (2019): 682-699. https://dx.doi.org/10.14573/altex.1909271

