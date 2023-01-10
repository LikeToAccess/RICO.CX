import time

from flask_login import UserMixin

from database import get_db


class User(UserMixin):
	def __init__(self, user_id, first_name, last_name, email, profile_pic,
				 account_created=None, banned=False):
		self.id = user_id
		self.first_name = first_name
		self.email = email
		self.profile_pic = profile_pic
		self.account_created = account_created
		self.banned = banned
		if last_name:
			self.last_name = last_name
			self.name = first_name + " " + last_name
		else:
			self.last_name = ""
			self.name = first_name

	@staticmethod
	def get(user_id):
		db = get_db()
		user = db.execute(
			"SELECT * FROM user WHERE user_id = ?", (user_id,)
		).fetchone()
		if not user:
			return None

		user = User(
			user_id=user[0],
			first_name=user[1],
			last_name=user[2],
			email=user[3],
			profile_pic=user[4],
			account_created=user[5],
			banned=user[6]
		)
		return user

	@staticmethod
	def get_all():
		db = get_db()
		users = db.execute(
			"SELECT * FROM user ORDER BY first_name ASC"
		).fetchall()
		if not users:
			return None

		user_list = []
		for user in users:
			user_list.append(
				User(
					user_id=user[0],
					first_name=user[1],
					last_name=user[2],
					email=user[3],
					profile_pic=user[4],
					account_created=user[5],
					banned=user[6]
				)
			)

		return user_list

	@staticmethod
	def create(user_id, first_name, last_name, email, profile_pic):
		db = get_db()
		db.execute(
			"INSERT INTO user (user_id, first_name, last_name, email, profile_pic, account_created) "
			"VALUES (?, ?, ?, ?, ?, ?)",
			(user_id, first_name, last_name, email, profile_pic, int(time.time()))
		)
		db.commit()

	def delete(self):
		db = get_db()
		db.execute(
			"DELETE FROM user WHERE user_id = ?", (self.id,)
		)
		db.execute(
			"DELETE FROM group_members WHERE user_id = ?", (self.id,)
		)
		db.commit()

	def ban(self):
		db = get_db()
		db.execute(
			"UPDATE user SET banned = TRUE WHERE user_id = ?", (self.id,)
		)
		self.banned = True
		db.commit()

	def unban(self):
		db = get_db()
		db.execute(
			"UPDATE user SET banned = FALSE WHERE user_id = ?", (self.id,)
		)
		self.banned = False
		db.commit()

	def change_role(self, role):
		if role == "None" or not role:
			return
		db = get_db()
		if role.isnumeric():
			role_id = role
		else:
			role_id = db.execute(
				"SELECT group_id FROM groups WHERE group_name = ?", (role,)
			).fetchone()[0]

		# Check if the user_id exists in group_members
		user_in_group = db.execute(
			"SELECT * FROM group_members WHERE user_id = ?", (self.id,)
		).fetchone()
		if user_in_group:
			db.execute(
				"UPDATE group_members SET group_id = ? WHERE user_id = ?", (role_id, self.id)
			)
		else:
			db.execute(
				"INSERT INTO group_members (user_id, group_id) VALUES (?, ?)", (self.id, role_id)
			)
		db.commit()
