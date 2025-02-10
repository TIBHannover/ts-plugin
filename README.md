# TS Plugin for TIB Terminology Service V2.0

The Plugin services for adding extra features to a Terminology Service. 

Implemented as part of [TIB](https://terminology.tib.eu/ts) and [NFDI4Chem](https://terminology.nfdi4chem.de/ts/) Terminology Services. 

Hosted: https://service.tib.eu/ts-plugin


![alt text](ts-Page-2.drawio.png)


## Tasks
- Authentication 
- Note for semantic artifacts
- Term request and issue report
- User defined Collection
- Advanced search setting storage
- Contact form
- Ontology suggestion


## Test
Activate the venv on your local machine and then run:

        :~$ python manage.py test



### Authentication code for testing
The authentication (test_login.py) Test part requires the login code as input. You need to manually create the login code by opening these links and authenticate yourself:

- Github: https://github.com/login/oauth/authorize?scope=user&client_id=b2c81399376da40700c9

- ORCID: https://sandbox.orcid.org/oauth/authorize?response_type=code&scope=/authenticate&client_id=APP-6W3MM8J52OXM6DYD&redirect_uri=http://www.localhost:3000/ts/

After you autheticate, copy the code (after code= in the url) in to the env variable name "GITHUB_LOGIN_CODE" and "ORCID_LOGIN_CODE" (for Github and ORCID) in the .env file.

### Other tests

For the other tests, just use a valid token in the .env file for test. (To avoid producing new login code each time). Vars to use are:

- GITHUB_TEST_ACCESS_TOKE
- ORCID_TEST_ACCESS_TOKE
- ORCID_LOGIN_USERNAME


## License

MIT License
