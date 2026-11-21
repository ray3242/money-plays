# Meridian architecture notes

Meridian is an e-commerce platform. Services: checkout-api, catalog, payments, pricing, cart,
search, billing, session-svc.

## Data

All transactional data lives in a 3-node YugabyteDB cluster (yb-node-1, yb-node-2, yb-node-3),
replication factor 3. Services reach YSQL through a connection pooler. Sessions are cached in Redis
(8 GB). Billing events flow through Kafka (topic billing-events, 12 partitions).

## Ownership

The on-call crew owns first response for every service. Changes go through the change gateway,
which enforces the production change policy.
