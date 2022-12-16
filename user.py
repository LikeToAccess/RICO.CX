import time

from flask_login import UserMixin

from database import get_db


class User(UserMixin):
	def __init__(self, user_id, first_name, last_name, email, profile_pic, account_created=None):
		self.id = user_id
		self.first_name = first_name
		self.email = email
		self.profile_pic = profile_pic
		self.account_created = account_created
		if last_name:
			self.last_name = last_name

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
		)
		return user

	@staticmethod
	def create(user_id, first_name, last_name, email, profile_pic):
		db = get_db()
		db.execute(
			"INSERT INTO user (user_id, first_name, last_name, email, profile_pic, account_created) "
			"VALUES (?, ?, ?, ?, ?, ?)",
			(user_id, first_name, last_name, email, profile_pic, int(time.time()))
		)
		db.commit()
