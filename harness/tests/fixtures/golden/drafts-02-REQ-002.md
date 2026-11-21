### Draft REQ-002 (story): Cancel an unshipped order

Status: draft · area orders · parent REQ-001 · priority not set

#### Intent

- Actor: Customer
- Need: Cancel an order before it ships
- Business value: Fewer support tickets
- Cites: example/shop#⁠7

#### Scope

In:
- Cancelling a whole order (cites example/shop#⁠7)

Out:
- Partial cancellation (cites A-001)

#### Acceptance criteria

- **REQ-002/AC-001** (positive; key: order / cancel-order / status)
  - Given: A customer with an unshipped order
  - When: The customer cancels the order
  - Then: The order status is cancelled
  - Cites: example/shop#⁠7
- **REQ-002/AC-002** (negative; key: order / cancel-order / status)
  - Given: A customer with an unshipped order
  - When: The customer cancels a shipped order
  - Then: The order status is cancelled
  - Cites: example/shop#⁠7

Rules relied on: none

#### Rule changes (need your acceptance)

- new (add): An order can be cancelled until it ships.

Quality: none: No quality target in the intake.

#### Permissions

- customer: may cancel own order before shipping; may not cancel a shipped order

#### Open points

- A-001 (open): Whole orders only.
- Q-001 (open, blocking): order / no target / refund method

Sources: example/shop#⁠7

Stage-1 draft: nothing is committed. To accept it, apply it in your own commit (S-BA-042).

---
Staff-Run-Id: 100-1  
Stage: 1 (advisory: comments only) · Model: claude-sonnet-5-5 · Staff commit: 0123456789abcdef0123456789abcdef01234567  
Run: https://github.com/example/shop/actions/runs/100/attempts/1
