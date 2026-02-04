---
github_issue: 11
---
# Deploy The Application

## Working directory

`~/Desktop/receipt-ranger`

## Contents

After putting the front-end together, we should deploy the application.  The main purpose is to be able to more easily use the application and to have it as a portfolio piece. Right now, I have to open my laptop and run the application via the CLI whenever I want to process receipts.  I would like to be able to have the application deployed to a website that I can use on my phone anywhere. So that if I get a receipt in the kitchen for instance, I can take a photo of it and the application will do the processing rather than having to take it into another room and use my laptop (or turn on a local server and then use my phone). 

The deployed site will need to be secure. In particular, we need to solve the problem of the Anthropic and OpenAI keys. Obviously, we can't just have the application use my keys always, since someone could hack into it and then make a lot of requests on my key. There will probably need to be a bring your own API key type solution where you access the application and it asks you to log in or input your key, as the application does now locally. 

See the following document. /Users/grahamnessler/Desktop/receipt-ranger/deploy/Host Your Streamlit App on AWS. Streamlit is an incredible framework… _ by Brett Olmstead _ Medium.pdf. After you look at this document, let me know if you think that these steps will be compatible with this application. Also, please give me a plan for how you think this should be deployed. Don't do any work until I approve the plan. 

## Acceptance criteria

- The Receipt Ranger application will be deployed to a place that makes it easy to use on a mobile phone. 
- The application will be secure, and it will prevent users from being able to spam my API key. 

