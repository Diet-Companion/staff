### Analyst: draft requirements and questions

Intake example/shop#⁠7 · area **orders** · batch 2

#### Decisions for you

> Decide first: Q-001 (refund method) and the new rule in REQ-002.
>
> Drafted one epic and two stories.

#### Questions

**Q-001** (**blocking** · blocks REQ-003/AC-001 · key: order / no target / refund method)

> Where does the refund go?

- a) Original payment method. **(recommended)**
- b) Store credit.

Recommended: **a**

Answer in a comment as `Q-001: b` (or free text); then comment `/analyst` to continue.

#### Drafts

- **REQ-001** (epic): Order cancellation
- **REQ-002** (story, parent REQ-001): Cancel an unshipped order
- **REQ-003** (story, parent REQ-001): Refund a cancelled order

Each draft follows in its own comment.

#### Open assumptions

- **A-001** (order / no target / partial cancellation): Whole orders only.

#### Answers applied

- REQ-002 `assumptions\[A-002\].status` from example/shop#⁠7 comment 1001

---
Staff-Run-Id: 100-1  
Stage: 1 (advisory: comments only) · Model: claude-sonnet-5-5 · Staff commit: 0123456789abcdef0123456789abcdef01234567  
Run: https://github.com/example/shop/actions/runs/100/attempts/1
