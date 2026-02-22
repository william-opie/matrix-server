# Backup and Restore

## Backup paths

Backup these directories:

- `data/postgres/`
- `runtime/synapse/`
- `data/bootstrap/`
- `data/admin-api/`

## Suggested backup cadence

- Daily incremental backups.
- Weekly full backups.
- Off-device copies strongly recommended.

## Restore (high level)

1. Stop services:

```bash
docker compose down
```

2. Restore backup directories.
3. Start services:

```bash
docker compose up -d
```

4. Validate:

- Users can log in.
- Existing rooms/history are present.
- Admin UI works.
