### 2026-07-12-core-Standardized API Response Architecture

A centralised response architecture using a shared success response helper function and a global DRF exception handler. A consistent API response for all APIViews across all apps can be achieved.

### 2026-07-12-accounts-Email-Based Identity Model

User an email-based user model aligned with Google OAuth. Used email as login identifier and Google's sub identifier as the identity to uniquely identify users in database.


### 2026-07-12-accounts-JWT Cookie Authentication Strategy

Used HttpOnly cookie-based JWT authentication, for that a custom authentication class is written on accounts/authentication.py. So, client side JS cannot access the cookies.
