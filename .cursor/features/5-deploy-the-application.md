---
github_issue: 11
---
# Deploy The Application

## Working directory

`~/Desktop/receipt-ranger`

## Contents

After putting the front-end together, we should deploy the application. I will probably use AWS, but I could use another platform. The main purpose is to be able to more easily use the application. Right now, I have to open my laptop And run the application via the CLI whenever I want to process receipts. Even when I have the front-end built up, I'm just going to have to do the same, except running the front-end in our browser. I would like to be able to have the application deployed to a website that I can use on my phone anywhere. So that if I get a receipt in the kitchen for instance, I can take a photo of it and the application will do the processing rather than having to take it into another room and use my laptop. 

The policy will need to be secure. In particular, we need to solve the problem of the Anthropic key. Obviously, we can't just have the application use my Anthropic key always, since someone could hack into it and then make a lot of requests on my key. There will probably need to be a bring your own API key type solution where you access the application and it asks you to log in or input your key. Probably logging in makes sense, logging into Anthropic. All that logic will have to be taken care of.

## Acceptance criteria

- The Receipt Ranger application will be deployed to a place that makes it easy to use on a mobile phone. 
- The application will be secure, and it will prevent users from being able to spam my API key. 

