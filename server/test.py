from realdebrid import RealDebrid

rd = RealDebrid()

link = rd.add_torrent("https://milkie.cc/api/v1/torrents/mhOpid3WdZS0/torrent?key=bEZnkBDkTsYQQDR%2BdeK7LlFUwbr6Qsjr")
print(rd.get_torrent_info(link["id"]))

print(link)
