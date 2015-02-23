OAuth2 Support
==============

websequencediagrams.com input:

    title OAuth2 on RelengAPI

    User Agent -> Client: Page Request
    Client -> User Agent: 302 Redirect to Authz Endpoint
    User Agent -> Authz Endpoint: Page Request
    note right of Authz Endpoint: No existing user session
    Authz Endpoint -> User Agent: 302 Login Page
    User Agent -> Login Endpoint: Page Request
    Login Endpoint -> User Agent: 401 Authenticate
    User Agent -> Login Endpoint: Page Request w/ LDAP creds
    Login Endpoint -> User Agent: 302 Authz Endpoint w/ session
    User Agent -> Authz Endpoint: Page Request
    Authz Endpoint -> User Agent: Confirimation Form
    User Agent -> Authz Endpoint: Form Submission "yes"
    Authz Endpoint -> User Agent: 302 Redirect to Client with authorization_code
    User Agent -> Client: Page Request w/ authorization_code
    Client -> Token Endpoint: Get Token w/ client authentication + authorization_code
    Token Endpoint -> Client: refresh_token and access_token
    Client -> Resource Endpoint: API request w/ access_token
    Resource Endpoint -> Client: API Response
    Client -> User Agent: Page
    note right of User Agent: ..access token expires..
    Client -> Resource Endpoint: API request w/ access_token
    Resource Endpoint -> Client: 401 Authenticate
    Client -> Token Endpoint: Get Token w/ client authentication + refresh_token
    Token Endpoint -> Client: refresh_token and access_token
    Client -> Resource Endpoint: API request w/ access_token
    Resource Endpoint -> Client: API Response

