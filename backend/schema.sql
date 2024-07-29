-- (Schema for postgresql)
CREATE TABLE IF NOT EXISTS users (
	id serial primary key,
	email text not null,
	password_hash text not null,
	totp_key text not null,
	created_at timestamp with time zone default now()
);

CREATE TABLE IF NOT EXISTS videos (
	id serial primary key,
	owner_id integer not null,
	filename text not null,
	object_name text unique not null,
	hash_sha256 text,
	created_at timestamp with time zone default now(),

	CONSTRAINT fk_user
	FOREIGN KEY(owner_id)
	REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS images (
	id serial primary key,
	video_id integer not null,
	object_name text unique not null,
	created_at timestamp with time zone default now(),

	CONSTRAINT fk_video
	FOREIGN KEY(video_id)
	REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS job_results (
	id serial primary key,
	video_id integer not null,
	-- most jobs consider themselves with the whole video
	image_id integer default null,
	job_type text not null,
	-- job_result is schemaless and structure will vary by job_type
	job_result jsonb not null,
	created_at timestamp with time zone default now(),

	CONSTRAINT fk_video
	FOREIGN KEY(video_id)
	REFERENCES videos(id),

	CONSTRAINT fk_image
	FOREIGN KEY(image_id)
	REFERENCES images(id)
);

