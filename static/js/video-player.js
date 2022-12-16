const container = document.querySelector(".container");
video = container.querySelector("video");
progressBar = container.querySelector(".progress-bar");
const playButton = container.querySelector(".play-pause i");


video.addEventListener("timeupdate", () => {
	progressBar.style.width = `${(video.currentTime / video.duration) * 100}%`;
});

playButton.addEventListener("click", () => {
	// if the video is paused, play it, else pause it
	video.paused ? video.play() : video.pause();
});

video.addEventListener("play", () => {
	// Replace the play icon with the pause icon
	playButton.classList.replace("fa-play", "fa-pause");
});

video.addEventListener("pause", () => {
	// Replace the play icon with the pause icon
	playButton.classList.replace("fa-pause", "fa-play");
});

