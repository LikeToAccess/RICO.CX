function submitSearch(query, first_result_only=false) {
	createPreloader();
	// button.setAttribute("style", "animation: pulsate-fwd 0.5s ease-in-out both;");
	if (first_result_only) {
		console.log("Submitting searchone for: "+ query);
		httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/searchone?query="+ query, handleSearchoneResponse);
	} else {
		console.log("Submitting search for: "+ query);
		httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/search?query="+ query, handleSearchResponse);
	}
}

function submitSearchOne(query) {
	submitSearch(query, first_result_only=true);
}

var form = document.getElementById("input-section");
var submit = document.getElementById("submit-button-id");
if (form) {
	form.addEventListener("submit", async function(e) {
		e.preventDefault();
		query = document.getElementById("search-term-id").value;
		submitSearchOne(query);
	});
}

function handlePopularOnClick() {
	submitSearch("https://gomovies-online.cam/all-films-2");
}

var video_id = document.getElementById("video-id");
if (video_id) {
	resume_video_url = getCookie("video_url");
	if (resume_video_url) {
		console.log("Resuming video from cookie");
		video_id.src = resume_video_url;
		showVideoPlayer();
	}
}

function createPreloader() {
	loadingWheel = document.createElement("div");
	loadingWheel.setAttribute("class", "preloader");
	document.body.appendChild(loadingWheel);
}

function removePreloader() {
	preloader = document.getElementsByClassName("preloader")[0];
	if (preloader) preloader.remove();
}

function handleSearchoneResponse(response) {
	// response always contains result data
	json = JSON.parse(response.responseText);
	// console.log("handleSearchoneResponse: "+ JSON.stringify(json.data));
	// console.log(json.data);
	// console.log(json.data.page_url);
	// document.getElementById("video-id").poster = json.data.poster_url;
	if (!video_id) return removePreloader();
	console.log("Running getvideo for: "+ json.data.page_url);
	httpGetAsync(
		API_HOST +":"+ API_PORT +"/api/v1/getvideo?page_url="+ json.data.page_url,
		handleGetvideoResponse
	);
}

function handleSearchResponse(response) {
	// response always contains result data
	json = JSON.parse(response.responseText);
	// console.log("Running getvideo for: "+ json.data.page_url);
	// console.log("handleSearchoneResponse: "+ JSON.stringify(json.data));
	console.log(json.data);
	// console.log(json.data.page_url);
	// document.getElementById("video-id").poster = json.data.poster_url;
	// httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/getvideo?page_url="+ json.data.page_url, handleGetvideoResponse);
	removePreloader();
}

function handleCaptchaResponse(response) {
	// response contains result data or captcha error
	json = JSON.parse(response.responseText);
	console.log(json.message);
	if (response.status == 200) {
		overlay = document.getElementsByClassName("overlay")[0];
		if (overlay) overlay.remove();
		httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/getvideo?page_url="+ json.data.page_url, handleGetvideoResponse);
	} else if (response.status == 225) {
		const captchaImage = json.data;
		const page_url = json.page_url;
		console.log("HTTP response status code: "+ response.status +"\n"+ json.message);
		captchaPopUp(captchaImage, page_url);
	}
}

function getCookie(cname) {
	// Credit: https://www.w3schools.com/js/js_cookies.asp
	let name = cname + "=";
	let decodedCookie = decodeURIComponent(document.cookie);
	let ca = decodedCookie.split(';');
	for(let i = 0; i <ca.length; i++) {
		let c = ca[i];
		while (c.charAt(0) == ' ') {
			c = c.substring(1);
		}
		if (c.indexOf(name) == 0) {
			return c.substring(name.length, c.length);
		}
	}
	return "";
}

function setCookie(name, value, expires) {
	var now = new Date();
	now.setTime(expires * 1000);
	var cookie = name +"="+ value +"; expires="+ now.toUTCString() +"; path=/";
	console.log(cookie);
	document.cookie = cookie;
}

function captchaPopUp(src, video_url) {
	// <div class="overlay">
	// 	<div id="captcha-container">
	// 		<p>Captcha!</p>
	// 		<img src="https://gomovies-online.cam/site/captcha" id="captcha-image" style="background:#fff;">
	// 		<form>
	// 			<input type="text" id="captcha-response-id">
	// 			<input type="submit" value="Submit" id="captcha-submit-button-id">
	// 		</form>
	// 	</div>
	// </div>
	var overlayElement = document.createElement("div");
	var captchaContainerElement = document.createElement("div");
	var captchaTitleElement = document.createElement("p");
	var captchaImageElement = document.createElement("img");
	var captchaFormElement = document.createElement("form");
	var captchaResponseElement = document.createElement("input");
	var captchaSubmitButtonElement = document.createElement("input");

	overlayElement.setAttribute("class", "overlay");
	overlayElement.setAttribute("style", "animation: fade-in 0.6s cubic-bezier(0.390, 0.575, 0.565, 1.000) both;");

	captchaContainerElement.setAttribute("id", "captcha-container");
	captchaContainerElement.setAttribute("style", "animation: slide-in-blurred-top 0.6s cubic-bezier(0.230, 1.000, 0.320, 1.000) both;");

	captchaTitleElement.innerText = "Captcha!";

	captchaImageElement.setAttribute("src", src);
	captchaImageElement.setAttribute("id", "captcha-image");

	captchaResponseElement.setAttribute("type", "text");
	captchaResponseElement.setAttribute("id", "captcha-response-id");

	captchaSubmitButtonElement.setAttribute("type", "submit");
	captchaSubmitButtonElement.setAttribute("value", "Submit");
	captchaSubmitButtonElement.setAttribute("id", "captcha-submit-button-id");

	document.body.appendChild(overlayElement);
	overlayElement.appendChild(captchaContainerElement);
	captchaContainerElement.appendChild(captchaTitleElement);
	captchaContainerElement.appendChild(captchaImageElement);
	captchaContainerElement.appendChild(captchaFormElement);
	captchaFormElement.appendChild(captchaResponseElement);
	captchaFormElement.appendChild(captchaSubmitButtonElement);

	captchaFormElement.addEventListener("submit", async function(e) {
		// captchaSubmitButtonElement.setAttribute("style", "animation: pulsate-fwd 0.5s ease-in-out both;");
		e.preventDefault();
		captchaResponse = captchaResponseElement.value;
		console.log("Submitting captcha response: "+ captchaResponse);
		httpPostAsync(API_HOST +":"+ API_PORT +"/api/v1/captcha?video_url="+ video_url +"&captcha_response="+ captchaResponse, handleCaptchaResponse);
	});
}

function closeLoginModal() {
	const loginModal = document.getElementById("login-modal");
	loginModal.style.display = "none";
}

function httpPostAsync(url, callback, method="POST") {
	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() {
		// console.log(xmlHttp);
		if (xmlHttp.readyState == 4 && (xmlHttp.status == 200 || xmlHttp.status == 225))
			callback(xmlHttp);
		else if (xmlHttp.readyState == 4 && xmlHttp.status != 200)
			alert(JSON.parse(xmlHttp.responseText).message);
			// callback(xmlHttp);
	};
	xmlHttp.open(method, url, true); // true for asynchronous
	xmlHttp.send(null);
}

function httpGetAsync(url, callback) {
	httpPostAsync(url, callback, method="GET");
}


// const video = document.getElementById("video");
// const play = document.getElementById("play");
// const pause = document.getElementById("pause");
// const stop = document.getElementById("stop");
// const backward = document.getElementById("backward");
// const forward = document.getElementById("forward");
// const volume = document.getElementById("volume");
// const playbackRate = document.getElementById("playbackRate");

// play.addEventListener("click", () => {
// 	video.play();
// });

// pause.addEventListener("click", () => {
// 	video.pause();
// });

// stop.addEventListener("click", () => {
// 	video.currentTime = 0;
// 	video.pause();
// });

// backward.addEventListener("click", () => {
// 	video.currentTime -= 5;
// });

// forward.addEventListener("click", () => {
// 	video.currentTime += 5;
// });

// volume.addEventListener("change", () => {
// 	video.volume = volume.value;
// });

// playbackRate.addEventListener("change", () => {
// 	video.playbackRate = playbackRate.value;
// });
