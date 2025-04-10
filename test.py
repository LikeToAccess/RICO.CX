def remove_non_ascii_encode(text):
    """Removes non-ASCII characters using encode/decode."""
    return text.encode("ascii", "ignore").decode("ascii")

my_string = "Star.Wars.Episode.IX.The.Rise.of.Skywalker.2020.1080p.AMZN.WEBRip.1600MB.DD5.1.x264-GalaxyRG ⭐😊" + ".mkv"
cleaned_string = remove_non_ascii_encode(my_string)
print(cleaned_string)
