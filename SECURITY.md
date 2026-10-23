# Security policy

## Reporting a vulnerability

Please report a vulnerability in this test suite, in an MFX Hub SDK, or in the MFX Hub API
privately:

- through GitHub's **Report a vulnerability** button on this repository's Security tab, or
- by email to **security@mfxhub.com**.

Please do not open a public issue, pull request or discussion for a security problem.

## What to expect

- We acknowledge a report within two business days.
- We tell you what we found and what we will do within ten business days.
- We fix what is confirmed and say when the fix is released. We credit you in the release notes if
  you want us to.

## What is in here

The suite holds no real credentials. Its signing key is the public test key from the API
description (seed bytes `00` to `1f`), and the fake server it ships listens on localhost only.
