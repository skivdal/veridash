-- name: GetDatabaseTime :one
SELECT now()::timestamptz AS database_time;
