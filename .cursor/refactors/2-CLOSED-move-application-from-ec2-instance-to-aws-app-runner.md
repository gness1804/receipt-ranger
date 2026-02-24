---
github_issue: 45
---
# Move application from EC2 instance to AWS App Runner

## Working directory

`~/Desktop/receipt-ranger`

## Contents

Currently, the application runs in an EC2 instance on AWS. This is cumbersome to maintain and costs more than app runner. Transitioning the application to App Runner would save money and make the application much easier to maintain.


## Acceptance criteria


- The application will be transitioned from an EC2 instance to AppRunner. 
- The application will be much easier to maintain on AppRunner. 
- The new setup should be modeled on the App Runner implementation for ~/Desktop/friendly-advice-columnist. 
- As with the friendly advice columnist implementation, there should be a deploy script which takes care of deployment and updates to app runner.

<!-- CLOSED -->
