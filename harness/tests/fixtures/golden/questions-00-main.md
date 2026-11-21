### Analyst: question batch

Intake example/shop#⁠7 · area **orders** · batch 1

#### Decisions for you

> Decide first: Q-001 (cancellation window) blocks every draft.
> The intake asks for order cancellation; no active rule covers it.

#### Questions

**Q-001** (**blocking** · blocks REQ-001 · key: order / no target / cancellation window)

> How long after placing an order may a customer cancel it?

- a) Until it ships. **(recommended)**
- b) Within 24 hours.
- c) Never; only support can cancel.

Recommended: **a**

**Q-002** (non-blocking · blocks REQ-001/AC-002 · key: order / cancel-order / refund method)

> Ping @⁠someone and see \[this\](https://example.invalid/x.png) \<b\>now\</b\> #⁠12 \* not a list

- a) Original payment method.
- b) Store credit. **(recommended)**

Recommended: **b**

Answer in a comment as `Q-001: b` (or free text); then comment `/analyst` to continue.

#### Open assumptions

- **A-001** (order / no target / partial cancellation): Whole orders only; overflow from the batch limit.

---
Staff-Run-Id: 100-1  
Stage: 1 (advisory: comments only) · Model: claude-sonnet-5-5 · Staff commit: 0123456789abcdef0123456789abcdef01234567  
Run: https://github.com/example/shop/actions/runs/100/attempts/1
