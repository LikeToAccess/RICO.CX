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

function showVideoPlayer() {
	document.getElementsByClassName("container")[0].removeAttribute("hidden");
}

function handleGetvideoResponse(response) {
	// response contains the direct video url or captcha error
	removePreloader();
	json = JSON.parse(response.responseText);
	console.log(json);
	if (response.status == 200) {
		// Play video
		console.log("Playing video");
		expires = json.data.split("~exp=")[1].split("~acl=/*~hmac=")[0];
		setCookie("video_url", json.data, expires);
		document.getElementById("video-id").src = json.data;
		showVideoPlayer();
	} else if (response.status == 225) {
		const captchaImage = json.data;
		const page_url = json.page_url;
		console.log("HTTP response status code: "+ response.status +"\n"+ json.message);
		captchaPopUp(captchaImage, page_url);
	}
}
