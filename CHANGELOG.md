# CHANGELOG

<!-- version list -->

## v2.13.0 (2026-02-24)

### Bug Fixes

- **.gitignore**: Add backups section
  ([`a0f52ef`](https://github.com/johannehouweling/ToxTempAssistant/commit/a0f52ef17a74a8e7745afb724fe13715ff1e1797))

### Features

- **backup**: Implement backup scheduler with cron job and environment configuration
  ([`dc46193`](https://github.com/johannehouweling/ToxTempAssistant/commit/dc46193016317318f98081ff3be008ff72ad218d))


## v2.12.4 (2026-02-23)

### Bug Fixes

- **backup**: Enhance retention cleanup with safety checks for BACKUP_ROOT and timestamp validation
  ([`39db889`](https://github.com/johannehouweling/ToxTempAssistant/commit/39db889d3f214f6470741f741ef87d125ed357e2))


## v2.12.3 (2026-02-23)

### Bug Fixes

- **backup**: Enhance MinIO mirror command with environment variables for endpoint and credentials
  ([`995c04c`](https://github.com/johannehouweling/ToxTempAssistant/commit/995c04c644b6db14c0712acdefd4f03ad8e7ee28))


## v2.12.2 (2026-02-23)

### Bug Fixes

- **env**: Correct BACKUP_ROOT path in .env.dummy [no-ci]
  ([`dbdc8ef`](https://github.com/johannehouweling/ToxTempAssistant/commit/dbdc8efb0f0857353eea2bfb013716fa71e486de))


## v2.12.1 (2026-02-23)

### Bug Fixes

- **backup**: Update MinIO mirror command to use local alias and correct destination path [no-ci]
  ([`813b14d`](https://github.com/johannehouweling/ToxTempAssistant/commit/813b14dbb6103ce089facf10874764c08172ee3a))


## v2.12.0 (2026-02-23)

### Chores

- **deps**: Bump aiohttp from 3.13.2 to 3.13.3
  ([`577f20c`](https://github.com/johannehouweling/ToxTempAssistant/commit/577f20c7fe3e4b5b67fd099bb13e690e333a41ea))

- **deps**: Bump cryptography from 46.0.3 to 46.0.5
  ([`e89f888`](https://github.com/johannehouweling/ToxTempAssistant/commit/e89f8880f34fb6f923d9b7e05372faa0c23a1439))

- **deps**: Bump django from 5.2.9 to 5.2.11
  ([`088404d`](https://github.com/johannehouweling/ToxTempAssistant/commit/088404da1f6277fd2168173a25b8a449dfedfa04))

- **deps**: Bump langchain-core from 0.3.80 to 0.3.81
  ([`656471a`](https://github.com/johannehouweling/ToxTempAssistant/commit/656471ad5f78266fd847efe8ca3f07c8f0f82305))

- **deps**: Bump urllib3 from 2.6.1 to 2.6.3
  ([`6cb327d`](https://github.com/johannehouweling/ToxTempAssistant/commit/6cb327d1f80f3b354accb6e9f16e859266631f95))

### Features

- **backup**: Add backup script and update .env for backup configuration [no-ci]
  ([`86b259e`](https://github.com/johannehouweling/ToxTempAssistant/commit/86b259e75357402889f2e8a89c734f4c22a6bde4))


## v2.11.1 (2026-01-20)

### Bug Fixes

- **forms**: Consent to upload files is no longer mandatory but actually optional with GDPR
  compliant details page.
  ([`036c613`](https://github.com/johannehouweling/ToxTempAssistant/commit/036c61336f44af82dbefda3083ac20dd1afc0eae))


## v2.11.0 (2026-01-19)

### Bug Fixes

- **ui**: Update busy status button to show loading spinner
  ([`f035981`](https://github.com/johannehouweling/ToxTempAssistant/commit/f0359816ef3f2c51c48f9ff4a15963310a8f4fe2))

### Features

- **ui**: Implement polling for assay status updates and add configuration for reload intervals
  ([`2b8248d`](https://github.com/johannehouweling/ToxTempAssistant/commit/2b8248d18bf590de35f1d0b7cf5cfdd250c8a517))


## v2.10.1 (2026-01-19)

### Bug Fixes

- **ui**: Enhance button tooltip messages for scheduled and busy statuses
  ([`e75830a`](https://github.com/johannehouweling/ToxTempAssistant/commit/e75830a39434dcb2882e17ff24b925de1af1db73))


## v2.10.0 (2026-01-19)

### Features

- **ui**: Add property to count answers found but not accepted and update progress bar rendering
  ([`2a0c5a7`](https://github.com/johannehouweling/ToxTempAssistant/commit/2a0c5a7e2825d99c3268bdbe163aaefc474b11c7))


## v2.9.2 (2026-01-13)

### Bug Fixes

- **demo**: Change filter to get for demo_assay retrieval
  ([`31cfe56`](https://github.com/johannehouweling/ToxTempAssistant/commit/31cfe56ccee8c9a9fc5088a8927a5b68fc4e62ef))

- **demo**: Fix the test to work with automatic signals based demo assay creation
  ([`42bc81b`](https://github.com/johannehouweling/ToxTempAssistant/commit/42bc81b9c611323cf7244edef33f592ad0a3e15d))

- **demo**: Test
  ([`ca5d186`](https://github.com/johannehouweling/ToxTempAssistant/commit/ca5d186bed46206d86cc7aae0b7342e634d756a5))

- **demo**: Wrong import path for seed_demo_assay_for_user func
  ([`a465848`](https://github.com/johannehouweling/ToxTempAssistant/commit/a465848812f650b872e1056bb5a92f1a5573874d))

- **signals**: Import signals module in app configuration to ensure signal handling
  ([`57671fe`](https://github.com/johannehouweling/ToxTempAssistant/commit/57671fefa3db7416437c5d37a023167b074820c2))

- **storages**: Remove broken orphaned file handling logic
  ([`f90745e`](https://github.com/johannehouweling/ToxTempAssistant/commit/f90745e433cee2b9a93c655379182f4c67c7733a))

- **storages**: Still remove dangling orphan function registration
  ([`42d1c18`](https://github.com/johannehouweling/ToxTempAssistant/commit/42d1c18d2e518ba53046ff8202f80b45bc86ea0a))


## v2.9.1 (2026-01-12)

### Bug Fixes

- <trigger release only>
  ([`961dc3c`](https://github.com/johannehouweling/ToxTempAssistant/commit/961dc3c6155f318be935df90e579154130cebeaa))

### Refactoring

- **demo**: Demo assays are now created when a new user is added to db from one central location
  (signals.py)
  ([`4434cd2`](https://github.com/johannehouweling/ToxTempAssistant/commit/4434cd2ae2fa76ed61350859d5e61a7921132825))


## v2.9.0 (2026-01-12)

### Bug Fixes

- **file storage**: Add logging for file downloads and implement download action for assays
  ([`80266b7`](https://github.com/johannehouweling/ToxTempAssistant/commit/80266b7142e9d7c0b6e6667322cb4088337d5368))

- **file storage**: Correct S3 object key format for user documents
  ([`1c93f42`](https://github.com/johannehouweling/ToxTempAssistant/commit/1c93f42d410d33f3188a5aa07fee3baf3eb1d34c))

- **file storage**: Fix how files are linked to assays
  ([`1d226cb`](https://github.com/johannehouweling/ToxTempAssistant/commit/1d226cb09ccd62da4adcdc6db3c085bc8488321a))

- **file storage**: Wrap zip_bytes in BytesIO for FileResponse in AssayAdmin
  ([`51589ca`](https://github.com/johannehouweling/ToxTempAssistant/commit/51589ca431d9b953d5274e87a3c5396704b67e5f))

- **image processing**: Increase minimum image dimensions and filter out small images in conversion
  ([`f68e9e3`](https://github.com/johannehouweling/ToxTempAssistant/commit/f68e9e3e5e65fba98b005a4c630224c6307b8d28))

- **storages**: Actually make AWS env vars availble to settings.py
  ([`cd33c48`](https://github.com/johannehouweling/ToxTempAssistant/commit/cd33c489ed14a06b53297507c5a6afd1ae32aed5))

- **storages**: Make sure that djangoapp has minio available
  ([`524f9e2`](https://github.com/johannehouweling/ToxTempAssistant/commit/524f9e201a1cf968458c0190eb456d015fbd13b3))

- **tests**: Update image sizes in PDF and DOCX extraction tests for consistency
  ([`28acf61`](https://github.com/johannehouweling/ToxTempAssistant/commit/28acf616d73ece5cbea1459e5d85f2a2ac74854c))

- **tests**: Update object key path in file storage consent test for accuracy
  ([`75c0cbf`](https://github.com/johannehouweling/ToxTempAssistant/commit/75c0cbf9329c15f0ffb77353ee99fc0dbd02e1cf))

### Chores

- **ci**: Update poetry lock
  ([`444dde5`](https://github.com/johannehouweling/ToxTempAssistant/commit/444dde54ed55dfa80397902fa3d6f465dfd63aa0))

### Features

- **factory**: Add factories for QuestionSet, Section, Subsection, Question, Answer, and FileAsset
  models
  ([`c89aae0`](https://github.com/johannehouweling/ToxTempAssistant/commit/c89aae009fcfc9b71227148920e0754e07e316c5))

- **file storage**: Implement user consent for file storage and add cleanup commands
  ([`9b5c43c`](https://github.com/johannehouweling/ToxTempAssistant/commit/9b5c43ce2e25f0f2131731d0121b7fd471fbfc6e))

- **uploadfiles**: Consent button on upload to store files for improvements.
  ([`6f5241c`](https://github.com/johannehouweling/ToxTempAssistant/commit/6f5241c2cfee8f343b4f488826c2933d33ec3a7f))

### Refactoring

- **tests**: Remove orphaned file cleanup tests
  ([`ee61d51`](https://github.com/johannehouweling/ToxTempAssistant/commit/ee61d51da010b0c4687b9d4bf54f7e8ca6e0426b))


## v2.8.0 (2026-01-11)

### Bug Fixes

- **storages**: Staticfiles on server as per usual
  ([`daba64b`](https://github.com/johannehouweling/ToxTempAssistant/commit/daba64b96f4fcdc75a8ee1c7275973f0951a4186))

- **ui**: Tighten helper text on StartingForm's FileField
  ([`6097abc`](https://github.com/johannehouweling/ToxTempAssistant/commit/6097abca35184157e5e482f6fc84f30890793fee))

### Features

- **new.html**: Add popover for file upload field help text with supported formats
  ([`9f1037d`](https://github.com/johannehouweling/ToxTempAssistant/commit/9f1037d4558fe1509ed160fc797ee6a4ad77c6a6))

- **storage**: Integrate django-storages for S3 support and update dependencies
  ([`9afbd34`](https://github.com/johannehouweling/ToxTempAssistant/commit/9afbd343ea387d1daafa322d08d3bbab435ebc54))

- **storages**: Add FileAsset and AnswerFile models with storage deletion logic
  ([`92d171b`](https://github.com/johannehouweling/ToxTempAssistant/commit/92d171b3072fb00f0a3a3e358008fd78b2c32df5))


## v2.4.1 (2026-01-10)

### Bug Fixes

- **minio**: Use latest version fo minio client
  ([`95a7274`](https://github.com/johannehouweling/ToxTempAssistant/commit/95a72740ece21488ae882af250dc19408e081d29))

### Chores

- **ci**: Bump version of actions
  ([`4446c57`](https://github.com/johannehouweling/ToxTempAssistant/commit/4446c57041205ace65642b1d3b2ca30cf184408a))


## v2.4.0 (2026-01-10)

### Bug Fixes

- **minio**: Add profiles
  ([`8572ba9`](https://github.com/johannehouweling/ToxTempAssistant/commit/8572ba9130514a97bf3bec4953332f0748bea7a0))

- **minio**: Attach minio to network
  ([`81a335b`](https://github.com/johannehouweling/ToxTempAssistant/commit/81a335b3afe69d2155052ed9b3e113eda801c061))

### Features

- **minio**: Add MinIO initialization script and update docker-compose
  ([`c29f9eb`](https://github.com/johannehouweling/ToxTempAssistant/commit/c29f9eb6d3a4a43840882716804f693e87de4840))


## v2.3.1 (2026-01-10)

### Bug Fixes

- **minio**: Correct Release
  ([`e387837`](https://github.com/johannehouweling/ToxTempAssistant/commit/e38783782975a1f69dc0db833b982479e798ed3d))


## v2.3.0 (2026-01-10)

### Bug Fixes

- **evaluation**: Update input directory path for quality scoring to use relative path
  ([`9f98a8e`](https://github.com/johannehouweling/ToxTempAssistant/commit/9f98a8e9f9d4844498648cf2cea7eb1df83af602))

- **poetry**: Update lockfile
  ([`2eb8988`](https://github.com/johannehouweling/ToxTempAssistant/commit/2eb898840d3b4deafb59fea9bf066913c9356a25))

- **poetry**: Update poetry lock file
  ([`2375150`](https://github.com/johannehouweling/ToxTempAssistant/commit/2375150c9c5f51558de295b9926dd0b64f4efb59))

### Chores

- **ci**: Deleted cleanup scripts
  ([`080070f`](https://github.com/johannehouweling/ToxTempAssistant/commit/080070fca32a8c35064703e0413b3748d6516219))

- **pyproject**: Update version to 2.2.0 and modify dependencies for compatibility
  ([`de8c089`](https://github.com/johannehouweling/ToxTempAssistant/commit/de8c08943687c462779e1ba49f4d93ae9ba627bb))

### Documentation

- **config**: Update notes on evaluation metrics and BERT usage in EvaluationConfig
  ([`4780266`](https://github.com/johannehouweling/ToxTempAssistant/commit/478026655ece897e4e1849f534d53c81f05f456c))

- **config**: Update notes on evaluation metrics and BERT usage in EvaluationConfig
  ([`d9eb306`](https://github.com/johannehouweling/ToxTempAssistant/commit/d9eb306b1bd750a04231dbd76c00c2554df3ff64))

- **urls**: Add example usage comment for init_db path
  ([`8ceea9f`](https://github.com/johannehouweling/ToxTempAssistant/commit/8ceea9fbfd0b11d92e8679b52e30dd72cbbf7267))

- **urls**: Add example usage comment for init_db path
  ([`0dae720`](https://github.com/johannehouweling/ToxTempAssistant/commit/0dae7205bef82a1cc15ad647a045225b7456392f))

### Features

- **data_analysis**: Update model handling and enhance scatter plot category orders for consistency
  ([`a401a23`](https://github.com/johannehouweling/ToxTempAssistant/commit/a401a2307051bcfc6db7d8782cf760112dc4e105))

- **evaluation**: Add validation metrics and BERT score options to ExperimentConfig and related
  functions
  ([`1bc2553`](https://github.com/johannehouweling/ToxTempAssistant/commit/1bc2553b496aa6a05790f87169129931c5994f3e))

- **evaluation**: Add validation metrics and BERT score options to ExperimentConfig and related
  functions
  ([`8b5f322`](https://github.com/johannehouweling/ToxTempAssistant/commit/8b5f322f45edb082d89b98030d2875f23a7c242f))

- **init_db**: Implement command to create QuestionSet from JSON file
  ([`b1438a2`](https://github.com/johannehouweling/ToxTempAssistant/commit/b1438a2000ca704b8f5c22ab67ad3a44995cf474))

- **init_db**: Implement command to create QuestionSet from JSON file
  ([`1cbc8fe`](https://github.com/johannehouweling/ToxTempAssistant/commit/1cbc8fee5d26fb5949b2d6fdc0bda110284892f6))

- **licenses**: Add third-party licenses documentation for OECD and EFSA materials
  ([`89d0cce`](https://github.com/johannehouweling/ToxTempAssistant/commit/89d0ccef98276f94ffb4ce964f504f10f6ade306))

- **minio**: Added minio for blob storage option
  ([`789ebb6`](https://github.com/johannehouweling/ToxTempAssistant/commit/789ebb6321755f2fc390602b55f2a599998396a4))

- **neg_summary, pooled_summary**: Refactor model file handling and enhance accuracy plotting with
  error bars
  ([`28d73e3`](https://github.com/johannehouweling/ToxTempAssistant/commit/28d73e3c3a22ba48a5146ecaa5e0b0025825b5c5))

- **pooled_summary**: Enhance accuracy scatter plot with improved legend and error bar labels
  ([`85e4b8f`](https://github.com/johannehouweling/ToxTempAssistant/commit/85e4b8f4cd68d6467be81fcfaf2c27f52919d4c1))

- **pooled_summary**: Enhance scatter plot styling with updated color and error bar settings
  ([`cfe6c9a`](https://github.com/johannehouweling/ToxTempAssistant/commit/cfe6c9aa681852b96a184e1a9533a6091051b98e))

- **questionset**: Enhance create_questionset_from_json to reuse existing QuestionSet if empty
  ([`d5e6470`](https://github.com/johannehouweling/ToxTempAssistant/commit/d5e6470c701ca1b29a86cf0d7bacd9ba37c06704))

- **questionset**: Enhance create_questionset_from_json to reuse existing QuestionSet if empty
  ([`cb2a708`](https://github.com/johannehouweling/ToxTempAssistant/commit/cb2a708145ea88342d721ca3dbdc53d0679851aa))

### Refactoring

- **data_analysis**: Add ncontrol_summary and pcontrol_summary scripts
  ([`d057ec7`](https://github.com/johannehouweling/ToxTempAssistant/commit/d057ec78b573ef2ce11deb67c671d893f934c86f))

- **data_analysis**: Remove unused neg_summary and pos_summary scripts; update pcontrol_summary for
  improved directory handling and output paths
  ([`f3780c7`](https://github.com/johannehouweling/ToxTempAssistant/commit/f3780c7d4bef6542466d4e7083d076f71ba9b874))

- **evaluation**: Remove BERT score option from ExperimentConfig
  ([`74f3e6e`](https://github.com/johannehouweling/ToxTempAssistant/commit/74f3e6e34d766800e1c8560e0a237ad1064658b4))

- **evaluation**: Remove BERT score option from ExperimentConfig
  ([`b64bb1c`](https://github.com/johannehouweling/ToxTempAssistant/commit/b64bb1cc68835bb1ad8d4dfbd8adcc442ab64345))


## v2.2.0 (2025-12-01)

### Bug Fixes

- **ci**: Prevent the lfs and throw away artifacts after a while
  ([`e717cbe`](https://github.com/johannehouweling/ToxTempAssistant/commit/e717cbe383fcec6baeb7d4a5618334e35ffe4b9f))

- **image**: Only extract image if extrac_images is True
  ([`c969183`](https://github.com/johannehouweling/ToxTempAssistant/commit/c9691838aa400995a4664be004b0aee02c8509c7))

### Chores

- **evaluation**: Restructure evalation folder
  ([`3b2c4f1`](https://github.com/johannehouweling/ToxTempAssistant/commit/3b2c4f14e252d896d79b3961b3a96daab7c57ff8))

- **gitignore**: Added .venv
  ([`4129966`](https://github.com/johannehouweling/ToxTempAssistant/commit/41299667360fcdf005caeadbbdfed06ae59d3a2d))

### Documentation

- **README**: Update terminology and improve clarity in evaluation pipeline documentation
  ([`800b2e3`](https://github.com/johannehouweling/ToxTempAssistant/commit/800b2e32a7115b5d76edc27f2224c16b9ae34aa1))

### Features

- **ci**: Add GitHub Actions workflow for Docker cleanup
  ([`4668ef3`](https://github.com/johannehouweling/ToxTempAssistant/commit/4668ef3f82bcece91965b3047373975aa76e07f6))

- **ci**: Added manual action to investigate space issues on runner
  ([`bf53812`](https://github.com/johannehouweling/ToxTempAssistant/commit/bf538122ce0b275768816c05af93c03bb68e67bc))

- **evaluation**: Enable per-experiment image extraction and update configurations
  ([`e1c16c7`](https://github.com/johannehouweling/ToxTempAssistant/commit/e1c16c7873d445bd721247376ebdfcf5e67f3b4b))

- **image**: Add minimum dimensions for image processing to filter out artifacts
  ([`099fea9`](https://github.com/johannehouweling/ToxTempAssistant/commit/099fea9202cfaea355313a195e596b0f6c4c4fc4))

- **image**: Convert incompatible images to webp
  ([`bf0f729`](https://github.com/johannehouweling/ToxTempAssistant/commit/bf0f7296918bdff46d9d78405b8f57ccfbb04b8b))

### Refactoring

- **ci**: Change file ending
  ([`03495e7`](https://github.com/johannehouweling/ToxTempAssistant/commit/03495e7e15655d74d071e2ad3f37c498953f8fb7))

- **ci**: Improve cleanup.yml with diagnostics and pruning
  ([`347a794`](https://github.com/johannehouweling/ToxTempAssistant/commit/347a794eccee1a7df9d3c1709e515c712b4bbf6c))

- **ci**: Put bertscore in speerate eval block for poetry
  ([`6fff216`](https://github.com/johannehouweling/ToxTempAssistant/commit/6fff21639fc2019e7d2807ec2e70fe3ae99e8931))

- **config**: Import default prompts from AppConfig for consistency
  ([`48b285f`](https://github.com/johannehouweling/ToxTempAssistant/commit/48b285f6deccbbb8124a43127bcf48a9345827fa))

- **data_analysis**: Streamline imports and adjust base directory paths in summary scripts
  ([`4c7e23c`](https://github.com/johannehouweling/ToxTempAssistant/commit/4c7e23cae1424b51f695f1a0e8c7b0a262b6b1aa))

- **evaluation**: Enhance experiment configuration summary and streamline output handling
  ([`8cdd5d5`](https://github.com/johannehouweling/ToxTempAssistant/commit/8cdd5d5feb6a17dcee99d3a72994ce344cfc0183))

- **evaluation**: Fixed run_evals cli
  ([`09f8406`](https://github.com/johannehouweling/ToxTempAssistant/commit/09f8406fe85ec023145e4b501cbf63413f6f18cc))

- **evaluation**: Refactor evaluation pipelines and management commands
  ([`1980035`](https://github.com/johannehouweling/ToxTempAssistant/commit/198003581d735627a351b71cb4d9ec026a268327))

- **evaluation**: Restructures folder structure and made run_eval a manage.py command. Provided raw
  .pdf input files via git lfs.
  ([`782c5de`](https://github.com/johannehouweling/ToxTempAssistant/commit/782c5de050ec7fce090688620925c823a662bcdc))

- **tests**: Update image handling in PDF and DOCX tests to use actualy small PNG image
  ([`ccd2d81`](https://github.com/johannehouweling/ToxTempAssistant/commit/ccd2d8147ad0bbbba50b22c63a47ed9524ed3439))


## v2.1.0 (2025-10-27)

### Features

- **goatcounter**: Add GoatCounter to toxtempassistant.vhp4safety.nl
  ([`fe2a52e`](https://github.com/johannehouweling/ToxTempAssistant/commit/fe2a52e8e18d212bba55b50536bf1e8cb9fffba6))


## v2.0.1 (2025-10-26)

### Bug Fixes

- **login**: Addd references to the intro text
  ([`8486d1b`](https://github.com/johannehouweling/ToxTempAssistant/commit/8486d1b54f6b712a28ce302a9e2e2e3a7283da9c))


## v2.0.0 (2025-10-26)

### Bug Fixes

- **debug**: For debug session make autogenerated templates optional
  ([`95f7475`](https://github.com/johannehouweling/ToxTempAssistant/commit/95f7475822d0765b289a9f3b12b8d847519d1ce7))

- **demo**: Users now get warnign when trying to overwrite the demo assay
  ([`f1405fd`](https://github.com/johannehouweling/ToxTempAssistant/commit/f1405fde5480ac46e181b1bd1fd9042783fb8852))

- **llm**: Fix single question answer.
  ([`715511d`](https://github.com/johannehouweling/ToxTempAssistant/commit/715511dcf323c3efb05307d13451154b01458ede))

- **new**: File select disabled now corrected
  ([`c54a29d`](https://github.com/johannehouweling/ToxTempAssistant/commit/c54a29da80da1e78ed2394c7a3fdf23ee3749de6))

- **overwrite**: Overwriting an existing assay is fixed
  ([`7b698e9`](https://github.com/johannehouweling/ToxTempAssistant/commit/7b698e945d1c2ab648de28e90b07b8d3439aad1d))

- **ui**: Reduce top space
  ([`a653c6d`](https://github.com/johannehouweling/ToxTempAssistant/commit/a653c6d8292ecb3d126e4725338750a26d54c36e))

### Features

- **answerupdate**: Also allow users to extract images from pdf for single answer updates
  ([`cb30eb0`](https://github.com/johannehouweling/ToxTempAssistant/commit/cb30eb0cd5c60482e4a00a73892d58781e6c3db8))

- **demo**: Read-only demo assays for new users
  ([`4f5649e`](https://github.com/johannehouweling/ToxTempAssistant/commit/4f5649e58c65d817cbad1488ccd952fcdfaf5545))

- **llm**: Asynchronous llm everywhere
  ([`c8cf162`](https://github.com/johannehouweling/ToxTempAssistant/commit/c8cf1628c0661b7985d26bc78350916d8c941ea1))

- **llm**: Extracts now images from the pdfs and use them as context for answering the toxtemp
  questions
  ([`92b6b45`](https://github.com/johannehouweling/ToxTempAssistant/commit/92b6b45e6261ac0ea3034469381f55728ad0312d))

- **overview**: Pagination also suitable for mobile 3 intermediates only
  ([`1339c04`](https://github.com/johannehouweling/ToxTempAssistant/commit/1339c04d814bc32148ffc721854a07ba56b4d756))

### Refactoring

- **oboarding**: Improve texts
  ([`d0b6729`](https://github.com/johannehouweling/ToxTempAssistant/commit/d0b67298fbc6efb27b9fa22a53b6db34890b4156))


## v1.25.1 (2025-10-23)

### Bug Fixes

- **overview**: Actually accessing the owner of the assay/investigation in the overview for admins.
  ([`fc8dfc7`](https://github.com/johannehouweling/ToxTempAssistant/commit/fc8dfc7b01fa324231e55d4ff5cfb806d959c55f))


## v1.25.0 (2025-10-23)

### Features

- **overview**: Show owner of toxtemp for superusers
  ([`8a5275b`](https://github.com/johannehouweling/ToxTempAssistant/commit/8a5275b170ad29e8063cf6d6faee2db0e833e720))


## v1.24.0 (2025-10-22)

### Bug Fixes

- **base**: Fixed padding on all pages
  ([`8d3f289`](https://github.com/johannehouweling/ToxTempAssistant/commit/8d3f2890800aa2269b66342cf682a75caf744bab))

- **beta**: Allow admins to bypass the beta sdmission check
  ([`15d7874`](https://github.com/johannehouweling/ToxTempAssistant/commit/15d787401fcf899c0ce7bec8e307ef96c8ffa35d))

- **onboardig**: Fixed automated onboarding, changed start.html to overview.html
  ([`530e81f`](https://github.com/johannehouweling/ToxTempAssistant/commit/530e81f0395f9b3c85dc1f4e0552f2e097cd4a19))

- **onboarding**: Fix placement of the toast
  ([`3380552`](https://github.com/johannehouweling/ToxTempAssistant/commit/3380552a11da4a0ae099932dfc119744c80ad373))

- **onboarding**: Fixed text
  ([`7a43983`](https://github.com/johannehouweling/ToxTempAssistant/commit/7a439833dcf7bb2c27c3596370da5a1b0bdc6e14))

- **onboarding**: Posiitioning left toast
  ([`4c01463`](https://github.com/johannehouweling/ToxTempAssistant/commit/4c01463a4ebedd9243e474f2465aae78a970216f))

- **onboarding**: Refined onboarding texts
  ([`5e1c0bf`](https://github.com/johannehouweling/ToxTempAssistant/commit/5e1c0bf04cd954ee45ef6a64007621f8e27a1ace))

### Features

- **onboarding**: Add multi-page guided tour with circular navigation
  ([`50f5178`](https://github.com/johannehouweling/ToxTempAssistant/commit/50f5178285ae59aa1c755dbfc33927c88a94e905))

- **onboarding**: Add previous button
  ([`0c91b76`](https://github.com/johannehouweling/ToxTempAssistant/commit/0c91b76302fd113b1d26d92174ca0e84668263a4))

- **onboarding**: Added onboarding for the answer page
  ([`8a6448c`](https://github.com/johannehouweling/ToxTempAssistant/commit/8a6448c2d1b404b543e6fc361f8587ae9dc52f4f))

- **toast**: Improved styling
  ([`5776472`](https://github.com/johannehouweling/ToxTempAssistant/commit/5776472724121f3c6150e407143de2c65b391d44))

### Refactoring

- **onboarding**: Changed back to dynamic placement of the toast
  ([`bd15a87`](https://github.com/johannehouweling/ToxTempAssistant/commit/bd15a8773c5dcd0b4b3cf5dabc19dada97921f98))

- **onboarding**: Clean up debug messages
  ([`c52fbf8`](https://github.com/johannehouweling/ToxTempAssistant/commit/c52fbf84bc997a433b14e2c163fd882017feb92d))

- **onboarding**: Fixed the toast to the center, added global step counter and made tied the
  individual tours together in one global tour
  ([`1dbe56e`](https://github.com/johannehouweling/ToxTempAssistant/commit/1dbe56eda14e77478b4d99fc69ea71daa21d6670))


## v1.23.0 (2025-10-01)

### Bug Fixes

- **ci**: Typo
  ([`ea41d91`](https://github.com/johannehouweling/ToxTempAssistant/commit/ea41d9160fc226793a22d678fec37e3848224411))

- **login**: Adjust badge position for sign-up button in login form
  ([`326d2f9`](https://github.com/johannehouweling/ToxTempAssistant/commit/326d2f94db7faab36212e5e2a35a95ddf8560c42))

### Features

- **login**: Replace static logos with a carousel for supported institutions
  ([`9789be4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9789be4deb84294863f7970527ca1646ec3d3b71))

- **login**: Update supported by section with institutional logos and remove feature list
  ([`b68de9f`](https://github.com/johannehouweling/ToxTempAssistant/commit/b68de9fa68306dd138364ab7b3040ad9ee82d6dc))

- **ui**: Added parnter logos
  ([`4997516`](https://github.com/johannehouweling/ToxTempAssistant/commit/49975165619b428d1bbf0716baaa81b792f64a50))


## v1.22.0 (2025-10-01)

### Bug Fixes

- **tests**: Introduce AdminFactory and refactor beta tests to use factories
  ([`ba75d05`](https://github.com/johannehouweling/ToxTempAssistant/commit/ba75d05299f6439f1eb57844ed428f490b289094))


## v1.21.3 (2025-09-25)

### Bug Fixes

- **ui**: Zenodo auto resolve link to most recent version
  ([`c538224`](https://github.com/johannehouweling/ToxTempAssistant/commit/c538224c1f8e7100ebedd73306faca54aee6836f))


## v1.21.2 (2025-09-25)

### Bug Fixes

- **ui**: Add zenodo doi link to config
  ([`3825ef3`](https://github.com/johannehouweling/ToxTempAssistant/commit/3825ef36467c33d32638402e9b6f90623f9de9d2))

- **ui**: Change link and svg to zenodo archive which points to newest version also on offcanvas
  ([`13e2fbf`](https://github.com/johannehouweling/ToxTempAssistant/commit/13e2fbf9fa4c4d48ccb5e851200e1c35a92803d8))


## v1.21.1 (2025-09-25)

### Bug Fixes

- **config**: Changed zenodo link to doi which refers always to the newest version
  ([`ab6a13c`](https://github.com/johannehouweling/ToxTempAssistant/commit/ab6a13cecad3a710cd32030122db197056334fbf))


## v1.21.0 (2025-09-22)

### Features

- **login**: Update description of ToxTempAssistant to clarify functionality and benefits
  ([`bbeca8d`](https://github.com/johannehouweling/ToxTempAssistant/commit/bbeca8d938c626cc605f54e664738f6f01f47f0e))


## v1.20.0 (2025-09-17)

### Features

- **email**: Add email configuration and send_email_task for sending emails (gmail for now)
  ([`adc7be8`](https://github.com/johannehouweling/ToxTempAssistant/commit/adc7be8c213dc2e93bef48b36da5bd1cfa71a527))


## v1.19.2 (2025-09-16)

### Bug Fixes

- **ui**: Export buttons on overview work now as expected
  ([`574370f`](https://github.com/johannehouweling/ToxTempAssistant/commit/574370fe4ad3894e114f32d5500513bbadd44685))


## v1.19.1 (2025-09-16)


## v1.19.0 (2025-09-16)

### Features

- **ui**: Login screen with explanation.
  ([`a3d7040`](https://github.com/johannehouweling/ToxTempAssistant/commit/a3d7040f827d1b95c158f6f5b8763237514a407c))


## v1.18.0 (2025-09-16)

### Features

- **export**: Add allowed export types to Config for improved validation
  ([`0a6cfe2`](https://github.com/johannehouweling/ToxTempAssistant/commit/0a6cfe25f378fe36d9d2c4df726e2a840b689bbd))


## v1.17.0 (2025-09-16)

### Features

- **db**: Added preferences field for Person
  ([#57](https://github.com/johannehouweling/ToxTempAssistant/pull/57),
  [`cd29891`](https://github.com/johannehouweling/ToxTempAssistant/commit/cd29891fea6aa972a463e0e2509f5366ee8c0043))

- **ui**: Add current URL context processor and update templates for improved navigation and
  onboarding ([#57](https://github.com/johannehouweling/ToxTempAssistant/pull/57),
  [`cd29891`](https://github.com/johannehouweling/ToxTempAssistant/commit/cd29891fea6aa972a463e0e2509f5366ee8c0043))

- **ui**: Show onboarding on first login
  ([#57](https://github.com/johannehouweling/ToxTempAssistant/pull/57),
  [`cd29891`](https://github.com/johannehouweling/ToxTempAssistant/commit/cd29891fea6aa972a463e0e2509f5366ee8c0043))


## v1.16.0 (2025-09-16)

### Bug Fixes

- **ui**: Rename create button to more generic save (because it also doubles as modify button in the
  respective context)
  ([`0196129`](https://github.com/johannehouweling/ToxTempAssistant/commit/01961297cf0dc4b65a646d6a632baf0ade3cfe85))

### Features

- **ui**: Overview buttons responsive with icons and text
  ([`99ea8a4`](https://github.com/johannehouweling/ToxTempAssistant/commit/99ea8a4133381cbb36c105f7c886e9d93964d77a))


## v1.15.1 (2025-09-16)

### Bug Fixes

- **ui**: Guided/help tour button
  ([`e1d2c51`](https://github.com/johannehouweling/ToxTempAssistant/commit/e1d2c51951745ba95c34615eb9ba61ca8b6a946e))


## v1.15.0 (2025-09-15)

### Bug Fixes

- **ui**: Allow upload dcument when new created assay
  ([#55](https://github.com/johannehouweling/ToxTempAssistant/pull/55),
  [`b2844c1`](https://github.com/johannehouweling/ToxTempAssistant/commit/b2844c124042e23d7cdf52ec5cc7d6d00e5be459))

### Features

- **ui**: ToxTempAssistant headline becomes link to return to main page.
  ([#55](https://github.com/johannehouweling/ToxTempAssistant/pull/55),
  [`b2844c1`](https://github.com/johannehouweling/ToxTempAssistant/commit/b2844c124042e23d7cdf52ec5cc7d6d00e5be459))


## v1.14.0 (2025-09-15)

### Bug Fixes

- **ui**: 1/n files on upload bar
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

- **ui**: Logic when to allow file-upload improved.
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

- **ui**: Offcanvas now compatible with additional modals
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

- **ui**: Upload bar
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

- **upload**: Handling of tempfiles
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

### Features

- **ui**: Progressbar during upload
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))

- **ui**: User Interface Improvements
  ([`9cd52f4`](https://github.com/johannehouweling/ToxTempAssistant/commit/9cd52f44de2d431af1d703a245a8fc5b4bcfbbd1))


## v1.13.0 (2025-09-15)

### Features

- **ui**: Added favicon
  ([`33f54d0`](https://github.com/johannehouweling/ToxTempAssistant/commit/33f54d03454e5fd1d9996e76e8f5a17223a566a1))


## v1.12.1 (2025-09-15)

### Bug Fixes

- **ui**: Margin for toxtempassistant logo match margin of user-menu
  ([`b551fb2`](https://github.com/johannehouweling/ToxTempAssistant/commit/b551fb208b3e2c005e91a1d94b8f4a572c54bf38))

- **ui**: Padding smaller
  ([`617e09d`](https://github.com/johannehouweling/ToxTempAssistant/commit/617e09df2c961c20702a3019f0c19195deb39f0b))


## v1.12.0 (2025-09-14)

### Features

- **ui**: Optimizations for small screens (responsiveness)
  ([`5b15096`](https://github.com/johannehouweling/ToxTempAssistant/commit/5b1509611ffe6111791d3eb2009d1f98c5507f5f))


## v1.11.2 (2025-09-14)


## v1.11.1 (2025-09-14)


## v1.11.0 (2025-09-14)

### Bug Fixes

- **ui**: Switched position of last_changed
  ([`a51c953`](https://github.com/johannehouweling/ToxTempAssistant/commit/a51c9536a30e6879b26c61c2dcf6984f280bb25d))

### Features

- **ci**: Include TAG and version in deploy and frontend
  ([`5e34dab`](https://github.com/johannehouweling/ToxTempAssistant/commit/5e34dab37e7882b74ce16ff9a0e026397e6b7a5f))


## v1.10.0 (2025-09-14)


## v1.9.1 (2025-09-14)

### Bug Fixes

- **export**: Update version and references in configuration; improve export filename and metadata
  ([`e530a43`](https://github.com/johannehouweling/ToxTempAssistant/commit/e530a4310cf0d01d4072afeb80e664d93f1a9748))


## v1.9.0 (2025-09-14)


## v1.8.1 (2025-09-14)

### Bug Fixes

- **logic**: Hide Assays that don't have a question_set attached to them
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))

- **ui**: Allow interaction with busy and scheduled buttons for tooltip toggling
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))

- **ui**: Distinguish assays by submission_data string in case of identical title
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))

- **ui**: Fix ui buttons in overview don't align up with delete.
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))

- **ui**: Protect overwriting existing ToxTemp, with overwrite checkbox
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))

### Refactoring

- **ui**: Added function description
  ([#49](https://github.com/johannehouweling/ToxTempAssistant/pull/49),
  [`c98318a`](https://github.com/johannehouweling/ToxTempAssistant/commit/c98318a683216f2b8d8c83c7337beccb933a77f4))


## v1.8.0 (2025-09-14)

### Features

- **config**: Increase max_size_mb from 20 to 30
  ([`e4d7c23`](https://github.com/johannehouweling/ToxTempAssistant/commit/e4d7c23a50df4cd01aee707ffe89c72a384c4855))

- **ui**: Add source parameter to delete_assay for better navigation
  ([`34a1034`](https://github.com/johannehouweling/ToxTempAssistant/commit/34a1034897204af807f377484acc5a968dd2e4bf))

### Refactoring

- Delete upload
  ([`6502595`](https://github.com/johannehouweling/ToxTempAssistant/commit/65025957f228be53920857fccc34fdaf3a736f27))

### Testing

- Add tests for AssayAnswerForm file upload handling
  ([`1d776e0`](https://github.com/johannehouweling/ToxTempAssistant/commit/1d776e04a2c27fa47bd877d8e480062f7c2dc146))


## v1.7.0 (2025-09-13)

### Bug Fixes

- **llm**: Allow missing OpenAI API key during testing
  ([`eec94ec`](https://github.com/johannehouweling/ToxTempAssistant/commit/eec94ec50973df064ac9681568296584fded9d66))

### Code Style

- **llm**: Format docstring for get_llm function for better readability
  ([`f5b837d`](https://github.com/johannehouweling/ToxTempAssistant/commit/f5b837d5fd434311b08a594a32d6bb6b19cb9726))

### Features

- **migrations**: Add new fields and alter existing fields in assay and questionset models
  ([`6a0df8c`](https://github.com/johannehouweling/ToxTempAssistant/commit/6a0df8c7e1e81230baa73b58203a6c8dd23ad7d9))

- **test**: Add comprehensive tests for DocumentDictFactory and process_llm_async functionality
  ([`f8cfafa`](https://github.com/johannehouweling/ToxTempAssistant/commit/f8cfafaae7ad4c5819462e022beca48d227e6f40))


## v1.6.3 (2025-09-13)

### Bug Fixes

- **ci**: PAT Token
  ([`29ae57f`](https://github.com/johannehouweling/ToxTempAssistant/commit/29ae57fc11ae1a41ecea0bfcdb3a63e7c2bc7b13))

- **ci**: Persists crentials and bump actions
  ([`a06d6f6`](https://github.com/johannehouweling/ToxTempAssistant/commit/a06d6f631001f3dfcd2d69d4b5f93a73edc3589c))

- **ci**: Reverse to PATOKEN [skip ci]
  ([`d3e5f23`](https://github.com/johannehouweling/ToxTempAssistant/commit/d3e5f23c53cb615963012ec9c50ce1a4df5c64aa))

- **ci**: Token
  ([`f4a4d7d`](https://github.com/johannehouweling/ToxTempAssistant/commit/f4a4d7d361d8c3eec0798ad9ca5f5e3a7e0d92da))

### Chores

- **ci**: Trigger build
  ([`73008af`](https://github.com/johannehouweling/ToxTempAssistant/commit/73008af5c3a08ad1394f9dd5829b46847f1fa7d2))


## v1.6.2 (2025-09-13)

### Bug Fixes

- **ci**: Change to hybrid GITHUB/PAT Token
  ([`e6b49ff`](https://github.com/johannehouweling/ToxTempAssistant/commit/e6b49ffa674d3ce4f7915d0b2035b315014a370b))


## v1.6.1 (2025-09-13)

### Bug Fixes

- **ci**: Change to github token for authentication
  ([`0ec61e4`](https://github.com/johannehouweling/ToxTempAssistant/commit/0ec61e4e683bfccf17eaa1e3934db54707d965e8))


## v1.6.0 (2025-09-13)

### Features

- **question**: Git commit -m ' update UI logic for new question set displa_
  ([#31](https://github.com/johannehouweling/ToxTempAssistant/pull/31),
  [`5f12fd7`](https://github.com/johannehouweling/ToxTempAssistant/commit/5f12fd78683fc486b6d9688ffce776e1fe1b6fe8))

- **question**: Update UI logic for new question set
  ([#31](https://github.com/johannehouweling/ToxTempAssistant/pull/31),
  [`5f12fd7`](https://github.com/johannehouweling/ToxTempAssistant/commit/5f12fd78683fc486b6d9688ffce776e1fe1b6fe8))

- **validation**: Enhance CSV generation with model name and overwrite option
  ([#31](https://github.com/johannehouweling/ToxTempAssistant/pull/31),
  [`5f12fd7`](https://github.com/johannehouweling/ToxTempAssistant/commit/5f12fd78683fc486b6d9688ffce776e1fe1b6fe8))


## v1.5.0 (2025-09-12)

### Chores

- Update dependencies ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

### Documentation

- Update toc ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

### Features

- Improve error reporting ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

- **debug**: Add INFO list of ENV variables
  ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

- **housekeeping**: Installed pre-commit, setup ruff as lint and fixed all ruff linting errors.
  ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

- **llm**: More robust error reporting
  ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))

### Refactoring

- Update folder structure ([#32](https://github.com/johannehouweling/ToxTempAssistant/pull/32),
  [`edfbd32`](https://github.com/johannehouweling/ToxTempAssistant/commit/edfbd32a212ae6fb67ba702235b9a82e874bfdc9))


## v1.4.0 (2025-08-12)

### Features

- **housekeeping**: Installed pre-commit, setup ruff as lint and fixed all ruff linting errors.
  ([`91391cc`](https://github.com/johannehouweling/ToxTempAssistant/commit/91391ccda4ae6f5961629726d1a6495a604d700f))


## v1.3.1 (2025-08-05)

### Bug Fixes

- **validation**: Update model imports and improve zip formatting in validation pipelines
  ([`c1236f7`](https://github.com/johannehouweling/ToxTempAssistant/commit/c1236f70506ba0824a7fdc6f20486dd8e793a154))


## v1.3.0 (2025-08-04)

### Bug Fixes

- **ci**: Attach docker default network
  ([`3977fef`](https://github.com/johannehouweling/ToxTempAssistant/commit/3977fef5d811be4a3c0a79c7b037b40ae1f95327))

- **ci**: Poetry run gunicorn
  ([`b4446aa`](https://github.com/johannehouweling/ToxTempAssistant/commit/b4446aa49efd4e050e3ab9af9c122ae654e74060))

- **ci**: QuestionSet model has Person as optional ForeignKey
  ([`5d3cd96`](https://github.com/johannehouweling/ToxTempAssistant/commit/5d3cd96106281197c26847da59643103db893cd6))

### Features

- **questionset**: Add visibility control
  ([#27](https://github.com/johannehouweling/ToxTempAssistant/pull/27),
  [`a8a5939`](https://github.com/johannehouweling/ToxTempAssistant/commit/a8a5939bcfac02b2ee3a3e91ab8639658095eec6))


## v1.2.2 (2025-08-01)

### Bug Fixes

- **ci**: TESTING bool from string
  ([`b3da36e`](https://github.com/johannehouweling/ToxTempAssistant/commit/b3da36ee6bf93082d2e5f35801ea3e629ba89871))


## v1.2.1 (2025-08-01)

### Bug Fixes

- **ci**: Preserve sudo env
  ([`5efbeb1`](https://github.com/johannehouweling/ToxTempAssistant/commit/5efbeb1a581b1119ae5053e074804c196fc67444))


## v1.2.0 (2025-08-01)

### Features

- **ci**: Only run release when pushing to main and then deploy
  ([`c4f275b`](https://github.com/johannehouweling/ToxTempAssistant/commit/c4f275bd5aaba4b9083f2905aa14a5ca416e7b83))


## v1.1.0 (2025-08-01)

### Bug Fixes

- **ci**: Add gha cache
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Allow pip to use system python in docker
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Buildx args
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Fancy reports
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Give postgres a chance to stop gracefully
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Only release on push to main
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Other fancy reporting tool
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Poetry inside venv
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Return to original fancy report
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Revert to docker compose
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Switch from python to docker
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Switch to docker compose
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Try isolate test, so can exit w code0
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Upload test-results
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Use buildx
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Use buildx fix env
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Use virtualenv by default
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Add testing echo
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Build for testing
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Export test-results / named folder in docker
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Forward build env to djangoapp env for TESTING
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Include dev packages for poetry install when under TESTING
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Poetry install
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Poetry only install extra for testing in docker
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Poetry without dev in production
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Position of --profile flag
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Remove depends on, to use profiles more flexibly
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Return to nc instead of pg_isready
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Set DJANGO_SETTINGS for pytest
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Set DJANGO_SETTINGS for pytest - correction
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Set TESTING ENV in docker build process
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **settings**: Testing flag wrong
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Djangoq not during testing
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Djangoq not during testing 2
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Pause testing for investigations
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Toggle .env.dummy also in docker-compose
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Use .env.dummy for testing
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

### Chores

- **debug**: Django startup/test
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **debug**: Dont report missing API Key as error during TESTING
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Added __init__
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

### Documentation

- Add content on testing
  ([`bdf9294`](https://github.com/johannehouweling/ToxTempAssistant/commit/bdf92948b1cf5731b4a7df1b623afe334519c61a))

- Added stub on testing
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

### Features

- **ci**: Added github actions to test, release and deploy automatically
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Coverage report
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **ci**: Integrate testing to github_actions
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Add profiles for test and prod
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Added first dummy test
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Added new env variables for test-db
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Load testing db in settings for tests
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **testing**: Testing inside docker
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

### Refactoring

- Move all tests to dedicated folder
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **depreciation**: __ instead of . for accessing model attributes
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Postgres port
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **docker**: Reintroduced depends on
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))

- **settings**: Simplify POSTGRES setup
  ([`349aec9`](https://github.com/johannehouweling/ToxTempAssistant/commit/349aec9361f15d16fc066e497e3441a77c06a57b))


## v1.0.11 (2025-07-30)

### Bug Fixes

- **ci**: Switch to PA TOKEN
  ([`407424c`](https://github.com/johannehouweling/ToxTempAssistant/commit/407424c97bdbf31c1995ea56f6fa9455e7b9fd5c))


## v1.0.10 (2025-07-30)

### Bug Fixes

- **ci**: Switch to PA TOKEN
  ([`d46fa92`](https://github.com/johannehouweling/ToxTempAssistant/commit/d46fa92637c374747bca25a56570ec330f334fc1))


## v1.0.9 (2025-07-30)

### Bug Fixes

- **ci**: Keep credentials
  ([`086e73f`](https://github.com/johannehouweling/ToxTempAssistant/commit/086e73f2a50002d078dc48f92864752c039ef505))

- **ci**: Switch back to token
  ([`c4bbeda`](https://github.com/johannehouweling/ToxTempAssistant/commit/c4bbeda22492e61681ffe3965c699e8a3bfbdf21))

- **ci**: Use token
  ([`5829818`](https://github.com/johannehouweling/ToxTempAssistant/commit/58298180a88265b89e99f20839ad7aa233fb6814))

- **ci**: Use token
  ([`8eae80e`](https://github.com/johannehouweling/ToxTempAssistant/commit/8eae80e7aff32824c0c49d693ce01c21ba92e50f))

- **ci**: Use token test GITHUBTOKEN
  ([`db53ce2`](https://github.com/johannehouweling/ToxTempAssistant/commit/db53ce209e4d2e39c752330021947d0192dd5198))

- **docker**: Install poetry when in home dir
  ([`b2a716d`](https://github.com/johannehouweling/ToxTempAssistant/commit/b2a716d100838a5abc7185ffd5d4735e125975f3))


## v1.0.8 (2025-07-30)

### Bug Fixes

- **docker**: Pipx install
  ([`c22df79`](https://github.com/johannehouweling/ToxTempAssistant/commit/c22df79f70f7fcd04241238562771772b8703882))


## v1.0.7 (2025-07-30)

### Bug Fixes

- **docker**: Poetry install
  ([`8fcf54a`](https://github.com/johannehouweling/ToxTempAssistant/commit/8fcf54ad640147c4ac5e368136e2bea174ed3cd1))


## v1.0.6 (2025-07-30)

### Bug Fixes

- **docker**: Poerty install
  ([`50efa47`](https://github.com/johannehouweling/ToxTempAssistant/commit/50efa473b64b6455b8508623e64c69cf1621729d))


## v1.0.5 (2025-07-30)

### Bug Fixes

- **model**: Make created_by optional for question_set
  ([`ed1e326`](https://github.com/johannehouweling/ToxTempAssistant/commit/ed1e326b58866869136ad007bbd0c1531ac7acab))


## v1.0.4 (2025-07-30)

### Bug Fixes

- **ci**: Removed TAG env from docker
  ([`2319d5c`](https://github.com/johannehouweling/ToxTempAssistant/commit/2319d5c5cd30058945060e4d7b9a7573ddd0629f))


## v1.0.3 (2025-07-30)


## v1.0.2 (2025-07-30)

### Bug Fixes

- **ci**: Debug
  ([`073de1c`](https://github.com/johannehouweling/ToxTempAssistant/commit/073de1c0e7456973b4fa0a45f31949e36812d60b))

- **ci**: Debug
  ([`29bc074`](https://github.com/johannehouweling/ToxTempAssistant/commit/29bc07487b6596fadfb3ebc1177d15149a14d323))

- **ci**: Debug sshkey for semantic release
  ([`19d4f72`](https://github.com/johannehouweling/ToxTempAssistant/commit/19d4f72e082cecc26ba7da98c564d891e03a10f4))

- **ci**: Push version in ssh-agent
  ([`d0e5d00`](https://github.com/johannehouweling/ToxTempAssistant/commit/d0e5d00d2d3688667e82d5b12c56ebacba1c49ad))

- **ci**: Try again with ssh
  ([`579a2b3`](https://github.com/johannehouweling/ToxTempAssistant/commit/579a2b31aa7efbeae45096fb1b87ae1aa0fd1533))

- **ci**: Type github
  ([`3c6a484`](https://github.com/johannehouweling/ToxTempAssistant/commit/3c6a4849f100598020ac06fad19ab48afbb8fb25))

- **ci**: Use consistent key
  ([`3efa239`](https://github.com/johannehouweling/ToxTempAssistant/commit/3efa239a2597ae40bdceab0c2fcad713c79aa395))

- **ci**: Use SSH instead of token
  ([`3b3674f`](https://github.com/johannehouweling/ToxTempAssistant/commit/3b3674ffde3a67ddafd8e3a6576679554021b4c8))


## v1.0.1 (2025-07-30)


## v1.0.0 (2025-07-30)

### Bug Fixes

- **ci**: 700 on .ssh permissions
  ([`71c0386`](https://github.com/johannehouweling/ToxTempAssistant/commit/71c038641a4f2c6ac26267b3f0eccb9aaaf2fff6))

- **ci**: Allow 0 major version for now
  ([`1d42322`](https://github.com/johannehouweling/ToxTempAssistant/commit/1d4232289e78d9163a7a84396a6f06e68407e21b))

- **ci**: Another try
  ([`c7c077e`](https://github.com/johannehouweling/ToxTempAssistant/commit/c7c077e434f43b4fbe55227873f7c94de09bad4c))

- **ci**: Bump semantic-release/git plugin version
  ([`59d6d40`](https://github.com/johannehouweling/ToxTempAssistant/commit/59d6d40575851df384b5e9733dd09c154ed46758))

- **ci**: Bump version of github actions
  ([`50faa90`](https://github.com/johannehouweling/ToxTempAssistant/commit/50faa90dc58623ba76b021b384e0ef8d8b959d99))

- **ci**: Change flag from --dev to --extras
  ([`90f6619`](https://github.com/johannehouweling/ToxTempAssistant/commit/90f6619106b1a8ac66837b684e404ff8a0e7fef4))

- **ci**: Debug release
  ([`179bbdf`](https://github.com/johannehouweling/ToxTempAssistant/commit/179bbdf0de377d39ddcba7d23eeabf9aafca4039))

- **ci**: Explicitly set write permissions for release workflow
  ([`55d88d2`](https://github.com/johannehouweling/ToxTempAssistant/commit/55d88d238ff1c51273bd14e023cc76c4b34ec851))

- **ci**: Fix config
  ([`0c151d5`](https://github.com/johannehouweling/ToxTempAssistant/commit/0c151d51c874c86f973aecf9dbe8e69a0941c9a3))

- **ci**: Inject the TOKEN explicitly
  ([`42fc204`](https://github.com/johannehouweling/ToxTempAssistant/commit/42fc20460d91b4cc991e46b0acf1e94105d159b2))

- **ci**: Install dev dependencies
  ([`f2e5a0c`](https://github.com/johannehouweling/ToxTempAssistant/commit/f2e5a0cac95b2f373f49aba6737d8bf7904c665c))

- **ci**: Reference TOKEN in pyproject
  ([`dc9eddb`](https://github.com/johannehouweling/ToxTempAssistant/commit/dc9eddbe3168f715c78566525f0beae747ba2140))

- **ci**: Remove verbose
  ([`4f62f07`](https://github.com/johannehouweling/ToxTempAssistant/commit/4f62f07968906e428b5693f6850d81a829f23f13))

- **ci**: Revert to action/setup-python
  ([`f5b3d30`](https://github.com/johannehouweling/ToxTempAssistant/commit/f5b3d30a82fc0016e8d862da43535f35bb1ada89))

- **ci**: Switch from publish to version
  ([`e7b5257`](https://github.com/johannehouweling/ToxTempAssistant/commit/e7b525792c0438a6e9a91b6d27eed4c77b437e06))

- **ci**: Toggle testing off
  ([`f87a261`](https://github.com/johannehouweling/ToxTempAssistant/commit/f87a2613b2ce2cd51fe199d421b120f65b6bdfd1))

- **ci**: Try action/semantic-release
  ([`af94168`](https://github.com/johannehouweling/ToxTempAssistant/commit/af941687b329a97c32801ff7dbdc2b1c99e8998a))

- **docs**: Small updates
  ([`db60958`](https://github.com/johannehouweling/ToxTempAssistant/commit/db609586fe269f6a581f3f240d7b1589dfc83641))

### Features

- **ci**: Added ci.yml to automate testing
  ([`6df91cd`](https://github.com/johannehouweling/ToxTempAssistant/commit/6df91cda9c301873fe66523ace1fa65aff5a0a0a))

- **package**: Switch requirements.txt to poetry
  ([`902c9ac`](https://github.com/johannehouweling/ToxTempAssistant/commit/902c9ac3ebf358d3263cf0407aee01d6780fb3ad))


## v0.9.1 (2025-06-18)


## v0.9.0 (2025-06-03)

- Initial Release
