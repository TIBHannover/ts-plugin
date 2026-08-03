Task:
- change the API response to send the jwt auth token in the header instead of the body

Details:
- The app at the moment sends the jwt token in the body of the response after login in "user/views.py" in the "login" function.
- The intention is to send the jwt via header instead of body and also receive via header (send by browser as cookie) instead of body.
- The goal is to reduce the client vulnerability to XSS attacks.
- For this task, you need to pay attention to the following directory also:
    - ../../../tib-ts/ 
    - this is the frontend app that uses the API.
    - any change you make here need to be reflected in the frontend app.
    - you are allowed therefore to make changes in the frontend app accordingly.
    - You need also prevent csrf attack by using csrf token alongside with the jwt token in the cookie.
- The app also has API users. Pay attention to not break the auth for the API users.
- All functionalities must be working as before. Only the auth for web users need to change.

Extras:
- The app runs in a docker container alongside with the database.
- therefore you don't have access to db on the host machine and cannot run the app without docker.

Caveat:
- this backend needs to support two frontends that are hosted on the different domains.
- Previously, this caused the cookie to not working since the browser does not allow.
- find a solution for this.
