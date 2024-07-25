CREATE TABLE videos (
	id serial primary key,
	filename text,
	object_name text unique,
	created_at timestamp with time zone default now()
);

