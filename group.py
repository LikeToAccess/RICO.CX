from database import get_db


class Group_Membership:
	def __init__(self, group_id, user_id, role):
		self.group_id = group_id
		self.user_id = user_id
		self.role = role

	@staticmethod
	def get(user_id):
		db = get_db()
		group_member = db.execute(
			"SELECT * FROM group_members WHERE user_id = ?", (user_id,)
		).fetchone()
		if not group_member:
			return None

		group_id = group_member[0]
		user_id = group_member[1]

		role = db.execute(
			"SELECT * FROM groups WHERE group_id = ?", (group_id,)
		).fetchone()[1]

		group_member = Group_Membership(
			group_id=group_id,
			user_id=user_id,
			role=role
		)
		return group_member

	@staticmethod
	def create(user_id, group_id):
		db = get_db()
		db.execute(
			"INSERT INTO group_members (user_id, group_id) "
			"VALUES (?, ?)",
			(user_id, group_id)
		)
		db.commit()
