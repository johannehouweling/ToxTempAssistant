# CHANGELOG

<!-- version list -->

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
