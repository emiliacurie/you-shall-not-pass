# A key leaked

Use this when a key, token, password or `.env` file was committed, pushed, pasted into a
chat, or shared anywhere it shouldn't be.

## 1. Calm them down

Say something like: "This happens a lot, and it can be fixed."

## 2. Explain in three short lines

- **The risk:** anyone who sees the key can use it as if they were you (spend money, see
  data).
- **The fix:** create a new key and cancel the old one. Deleting the key from the code is
  not enough: copies stay in git history, in other people's copies and in caches.
- **What breaks:** anything still using the old key (the app, the deploy, teammates'
  setups) stops working until it gets the new one.

## 3. Ask who will handle it

"Will someone else handle this, or will you?"

### Someone else handles it

Help them write a short message to the developer or whoever owns the key:

- which key it is (the service, e.g. "the Stripe test key"), never the key itself
- where it leaked (commit, branch, PR, chat, screenshot)
- when it happened
- whether the repository is public or private

### They handle it

Give the steps one at a time, in this order, so as little as possible breaks:

1. Create a new key on the service's website.
2. Put the new key in `.env` and anywhere else the app uses it (hosting settings,
   teammates' setups). Ask the person where those are; don't guess.
3. Check the app still works.
4. Cancel (revoke) the old key on the service's website.
5. Remove the key from the code and make sure `.env` is in `.gitignore`.

**Exception: if the repository is public, cancel the old key first.** Leaked keys in
public repos are found by bots within minutes. A short outage is better than a stranger
using the key.

Don't rewrite git history to "erase" the key unless a developer asks for it. Once the
key is cancelled, the old copy is harmless.
