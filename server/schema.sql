CREATE TABLE user (
	user_id TEXT PRIMARY KEY,
	first_name TEXT NOT NULL,
	last_name TEXT NOT NULL,
	email TEXT NOT NULL UNIQUE,
	profile_pic TEXT NOT NULL,
	account_created REAL NOT NULL,
	banned INTEGER DEFAULT FALSE NOT NULL
);

CREATE TABLE groups (
	group_id TEXT PRIMARY KEY,
	group_name TEXT NOT NULL
);

CREATE TABLE group_members (
	group_id TEXT,
	user_id TEXT,
	PRIMARY KEY (user_id, group_id),
	FOREIGN KEY (group_id)
		REFERENCES groups (group_id)
			ON DELETE CASCADE 
        	ON UPDATE NO ACTION,
	FOREIGN KEY (user_id)
		REFERENCES user (user_id)
			ON DELETE CASCADE 
			ON UPDATE NO ACTION
);

CREATE TABLE downloads (
	download_filename TEXT PRIMARY KEY,
	download_url TEXT NOT NULL,
	download_size INTEGER,
	download_quality TEXT,
	last_updated REAL NOT NULL,
	user_id TEXT NOT NULL,
	download_status TEXT DEFAULT "not_started" NOT NULL,
	FOREIGN KEY (user_id)
		REFERENCES user (user_id)
			ON DELETE CASCADE
			ON UPDATE NO ACTION
);


INSERT INTO main.groups (group_id, group_name) VALUES
	("100", "Standard Users"),
	("101", "Ad-Free Users"),
	("102", "Premium Users"),
	("103", "Beta Users"),
	("0", "Root"),
	("1", "Administrators"),
	("2", "Moderators");
INSERT INTO main.group_members (group_id, user_id) VALUES
	("1", "103686541999087786295"), -- anelson0421216@gmail.com
	("1", "108802760954752258469"); -- igeussbill@gmail.com
