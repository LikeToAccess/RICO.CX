function submitSearch(query, first_result_only=false) {
	createPreloader();
	// button.setAttribute("style", "animation: pulsate-fwd 0.5s ease-in-out both;");
	if (first_result_only) {
		console.log("Submitting searchone for: "+ query);
		httpGetAsync(API_HOST +":"+ API_PORT +"/api/v2/searchone?q="+ query, handleSearchoneResponse);
	} else {
		console.log("Submitting search for: "+ query);
		httpGetAsync(API_HOST +":"+ API_PORT +"/api/v2/search?q="+ query, handleSearchResponse);
	}
}

function submitSearchOne(query) {
	submitSearch(query, first_result_only=true);
}

const sleep = (milliseconds) => {
	return new Promise(resolve => setTimeout(resolve, milliseconds));
};

var form = document.getElementById("input-section");
var submit = document.getElementById("submit-button-id");
if (form) {
	form.addEventListener("submit", async function(e) {
		e.preventDefault();
		query = document.getElementById("search-term-id").value;
		submitSearch(query);
	});
}

function handlePopularOnClick() {
	createPreloader();
	httpGetAsync(API_HOST +":"+ API_PORT +"/api/v2/popular", handleSearchResponse);
}

// var video_id = document.getElementById("video-id");
// if (video_id) {
// 	resume_video_url = getCookie("video_url");
// 	if (resume_video_url) {
// 		console.log("Resuming video from cookie");
// 		video_id.src = resume_video_url;
// 		showVideoPlayer();
// 	}
// }

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
		API_HOST +":"+ API_PORT +"/api/v2/getvideo?page_url="+ json.data.page_url,
		handleGetvideoResponse
	);
}

// function wrapTextAtPeriodsAndSpaces(element) {
// 	const originalText = element.textContent;
// 	const newText = originalText.replace(/([. ])/g, "$1\u200B");
// 	element.textContent = newText;
// }

function startCardSpinner(id, spinner_file="/static/img/spinner.svg") {
	/*
	<div class="search-result" id="id-0">
		<img src="https://image.tmdb.org/t/p/w200/kNOFPQrel9YFCVzI0DF8FnCEpCw.jpg" class="result-thumbnail" onclick="startDownload(&quot;https://1337x.to/torrent/2968556/North-by-Northwest-1959-BluRay-1080p-YTS-YIFY/&quot;, 0);">
		<p class="result-title">North by Northwest</p>
		<p class="result-subtitle">North by Northwest (1959) [BluRay] [1080p] [YTS] [YIFY]</p>
		<p class="result-year label"> 1959 </p>
		<p class="result-score label"> 80% </p>
		<p class="result-duration label"> 136 min </p>
		<p class="result-quality label" style="background-color: #679ABC;"> FHD </p>
	</div>
	*/
	var spinner_container = document.createElement("div");
	var spinner = document.createElement("img");
	var result = document.getElementById("id-"+ id);
	var result_thumbnail = result.getElementsByClassName("result-thumbnail")[0];

	spinner_container.setAttribute("class", "spinner-container masked");
	spinner_container.setAttribute("style", "cursor: url('/static/img/not-allowed.svg'), not-allowed;");
	spinner_container.appendChild(spinner);

	spinner.setAttribute("src", spinner_file);
	spinner.setAttribute("class", "spinner");
	spinner.setAttribute("style", "animation: swirl-in-fwd 0.6s ease-out both;");

	result_thumbnail.setAttribute("style", "filter: url(#svg-blur); cursor: url('/static/img/not-allowed.svg'), not-allowed;");
	result_thumbnail.removeAttribute("onclick");

	result.appendChild(spinner_container);

	return [spinner_container, spinner, result_thumbnail];
}

function wrapTextAtPeriods(element) {
	const original_text = element.textContent;
	const new_text = original_text.replace(/\./g, ".\u200B");
	element.textContent = new_text;
}

function startDownload(url, id) {
	startCardSpinner(id);
	httpPostAsync(API_HOST +":"+ API_PORT +`/api/v2/download?page_url=${encodeURIComponent(url)}&id=${id}`, handleDownloadResponse);
}

function handleSearchResponse(response) {
	// response always contains result data
	json = JSON.parse(response.responseText);
	// console.log("Running getvideo for: "+ json.data.page_url);
	// console.log("handleSearchoneResponse: "+ JSON.stringify(json.data));
	console.log(json.data);
	// console.log(json);
	// console.log(json.data.page_url);
	// document.getElementById("video-id").poster = json.data.poster_url;
	// httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/getvideo?page_url="+ json.data.page_url, handleGetvideoResponse);
	removePreloader();
	// {% for result in results %}
	// 	{% set poster   = result["poster_url"]           %}
	// 	{% set title    = result["title"]                %}
	// 	{% set year     = result["data"]["release_year"] %}
	// 	{% set imdb     = result["data"]["imdb_score"]   %}
	// 	{% set duration = result["data"]["duration"]     %}
	// 	<div class="search-result">
	// 		<img id="{{ index }}" src="{{ poster }}" class="result-thumbnail" onclick="onItemClick({{ result }});">
	// 		<p class="result-title">{{ title }}</p>
	// 		<p class="result-year label"> {{ year }} </p>
	// 		<p class="result-score label"> {{ imdb }} </p>
	// 		<p class="result-duration label"> {{ duration }} </p>
	// 	</div>
	// {% endfor %}
	results_section = document.getElementById("results-section");
	results_section.innerHTML = "";
	results = json.data;
	// for (let i = 0; i < results.length; i++) {
	results.forEach(async function(result, i) {
		// result   = results[i];
		poster   = result.poster_url;
		title    = result.title;
		subtitle = result.original_title;
		year     = result.release_year;
		score    = result.score;
		duration = result.duration;
		quality  = result.quality_tag;
		// page_url = result.page_url;
		var search_result = document.createElement("div");
		search_result.setAttribute("class", "search-result");
		search_result.setAttribute("style", "animation: swing-in-top-bck 0.6s cubic-bezier(0.175, 0.885, 0.320, 1.275) "+ parseInt(i)/20 +"s both;"); // parseInt is returning NaN
		search_result.setAttribute("id", "id-"+ i);
		// search_result.setAttribute("data-page-url", page_url);
		// search_result.setAttribute("onclick", "onItemClick(this);");
		var page_url = result.page_url;
		result = JSON.stringify(result);
		// console.log("result: "+ result);
		// console.log(`result: ${encodeURIComponent(result)}`);
		search_result.innerHTML = `
			<img src="${poster}" class="result-thumbnail" onclick='startDownload("${page_url}", ${i});'>
			<p class="result-title">${title}</p>
			<p class="result-subtitle">${subtitle}</p>
			<p class="result-year label"> ${year} </p>
			<p class="result-score label"> ${score} </p>
			<p class="result-duration label"> ${duration} min </p>
		`;
		if (quality == "CAM" || quality == "SD")
			search_result.innerHTML += `\n<p class="result-quality label"> ${quality} </p>`;
		else if (quality == "HD")
			search_result.innerHTML += `\n<p class="result-quality label" style="background-color: #679ABC;"> ${quality} </p>`;
		else if (quality == "FHD")
			search_result.innerHTML += `\n<p class="result-quality label" style="background-color: #679ABC;"> ${quality} </p>`;
		else if (quality == "UHD")
			search_result.innerHTML += `\n<p class="result-quality label" style="background-color: #679ABC;"> ${quality} </p>`;
		results_section.appendChild(search_result);
		const subtitleParagraphs = document.querySelectorAll('p.result-subtitle'); // Select only p.result-subtitle
		subtitleParagraphs.forEach(p => wrapTextAtPeriods(p));

		await sleep(600 + i/0.02);
		search_result.removeAttribute("style");
		// search_result.setAttribute("style", "");
		// console.log("search_result: "+ search_result);
	});
}

// function onItemClick(page_url) {
// 	httpPostAsync(API_HOST +":"+ API_PORT +"/api/v2/download?page_url="+ page_url, handleDownloadResponse);
// }

// function handleDownloadResponse(response) {
// 	console.log("handleDownloadResponse: "+ response);
// }

// DEPRICATED FUNCTION
// function handleCaptchaResponse(response) {
// 	// response contains result data or captcha error
// 	json = JSON.parse(response.responseText);
// 	console.log(json.message);
// 	if (response.status == 200) {
// 		overlay = document.getElementsByClassName("overlay")[0];
// 		if (overlay) overlay.remove();
// 		// httpGetAsync(API_HOST +":"+ API_PORT +"/api/v1/getvideo?page_url="+ json.data.page_url, handleGetvideoResponse);
// 		httpPostAsync(API_HOST +":"+ API_PORT +"/api/v2/download?url="+ json.page_url, handleDownloadResponse);
// 	} else if (response.status == 225) {
// 		const captchaImage = json.data;
// 		const page_url = json.page_url;
// 		console.log("HTTP response status code: "+ response.status +"\n"+ json.message);
// 		captchaPopUp(captchaImage, page_url);
// 	}
// }

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

// DEPRICATED FUNCTION
// function captchaPopUp(src, page_url) {
// 	// <div class="overlay">
// 	// 	<div id="captcha-container">
// 	// 		<p>Captcha!</p>
// 	// 		<img src="https://gomovies-online.cam/site/captcha" id="captcha-image" style="background:#fff;">
// 	// 		<form>
// 	// 			<input type="text" id="captcha-response-id">
// 	// 			<input type="submit" value="Submit" id="captcha-submit-button-id">
// 	// 		</form>
// 	// 	</div>
// 	// </div>
// 	var overlayElement = document.createElement("div");
// 	var captchaContainerElement = document.createElement("div");
// 	var captchaTitleElement = document.createElement("p");
// 	var captchaImageElement = document.createElement("img");
// 	var captchaFormElement = document.createElement("form");
// 	var captchaResponseElement = document.createElement("input");
// 	var captchaSubmitButtonElement = document.createElement("input");

// 	overlayElement.setAttribute("class", "overlay");
// 	overlayElement.setAttribute("style", "animation: fade-in 0.6s cubic-bezier(0.390, 0.575, 0.565, 1.000) both;");

// 	captchaContainerElement.setAttribute("id", "captcha-container");
// 	captchaContainerElement.setAttribute("style", "animation: slide-in-blurred-top 0.6s cubic-bezier(0.230, 1.000, 0.320, 1.000) both;");

// 	captchaTitleElement.innerText = "Captcha!";

// 	captchaImageElement.setAttribute("src", src);
// 	captchaImageElement.setAttribute("id", "captcha-image");

// 	captchaResponseElement.setAttribute("type", "text");
// 	captchaResponseElement.setAttribute("id", "captcha-response-id");

// 	captchaSubmitButtonElement.setAttribute("type", "submit");
// 	captchaSubmitButtonElement.setAttribute("value", "Submit");
// 	captchaSubmitButtonElement.setAttribute("id", "captcha-submit-button-id");

// 	document.body.appendChild(overlayElement);
// 	overlayElement.appendChild(captchaContainerElement);
// 	captchaContainerElement.appendChild(captchaTitleElement);
// 	captchaContainerElement.appendChild(captchaImageElement);
// 	captchaContainerElement.appendChild(captchaFormElement);
// 	captchaFormElement.appendChild(captchaResponseElement);
// 	captchaFormElement.appendChild(captchaSubmitButtonElement);

// 	captchaFormElement.addEventListener("submit", async function(e) {
// 		// captchaSubmitButtonElement.setAttribute("style", "animation: pulsate-fwd 0.5s ease-in-out both;");
// 		e.preventDefault();
// 		captchaResponse = captchaResponseElement.value;
// 		console.log("Submitting captcha response: "+ captchaResponse);
// 		httpPostAsync(API_HOST +":"+ API_PORT +"/api/v1/captcha?page_url="+ page_url +"&captcha_response="+ captchaResponse, handleCaptchaResponse);
// 	});
// }

function closeLoginModal() {
	const loginModal = document.getElementById("login-modal");
	loginModal.style.display = "none";
}

function httpPostAsync(url, callback, method="POST") {
	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() {
		// console.log(xmlHttp);
		if (xmlHttp.readyState == 4 && [200, 225].includes(xmlHttp.status))
			callback(xmlHttp);
		else if (xmlHttp.readyState == 4 && ![200, 201].includes(xmlHttp.status)) {
			removePreloader();
			try {
				alert(JSON.parse(xmlHttp.responseText).message);
			} catch(error) {
				alert(xmlHttp.responseText);
			}
		} else if (xmlHttp.readyState == 4 && xmlHttp.status == 404)
			removePreloader();
			// callback(xmlHttp);
	};
	xmlHttp.open(method, url, true); // true for asynchronous
	xmlHttp.send(null);
}

function httpGetAsync(url, callback) {
	httpPostAsync(url, callback, method="GET");
}

// create a profile dropdown menu
function createProfileDropdownMenu(profile_pic, profile_name, group_name) {
	var profileDropdownMenu = document.createElement("div");
	var profileDropdownContent = document.createElement("div");
	var profileDropdownInfo = document.createElement("div");
	var profileDropdownImg = document.createElement("img");
	var profileDropdownName = document.createElement("p");
	var profileDropdownLink1 = document.createElement("a");

	profileDropdownMenu.setAttribute("class", "dropdown");
	profileDropdownContent.setAttribute("class", "dropdown-content");
	profileDropdownInfo.setAttribute("class", "profile-dropdown-info");
	profileDropdownLink1.setAttribute("href", "logout");

	profileDropdownImg.setAttribute("src", profile_pic);
	profileDropdownName.innerText = profile_name;
	profileDropdownLink1.innerText = "Logout";

	profileDropdownMenu.appendChild(profileDropdownContent);
	profileDropdownContent.appendChild(profileDropdownInfo);
	profileDropdownInfo.appendChild(profileDropdownImg);
	profileDropdownInfo.appendChild(profileDropdownName);
	profileDropdownContent.appendChild(profileDropdownLink1);
	// console.log(group_name);
	if (["Moderators", "Administrators", "Root"].includes(group_name)) {
		var profileDropdownLink2 = document.createElement("a");
		profileDropdownLink2.setAttribute("href", "admin");
		profileDropdownLink2.innerText = "Admin Portal";
		profileDropdownContent.appendChild(profileDropdownLink2);
	}

	return profileDropdownMenu;
}

function toggleProfileDropdownMenu(profile_pic, profile_name, group_name) {
	// check if the dropdown does not yet exist and create it
	if (document.getElementById("profile-dropdown-menu") == null) {
		var profileDropdownMenu = createProfileDropdownMenu(profile_pic, profile_name, group_name);
		profileDropdownMenu.setAttribute("id", "profile-dropdown-menu");
		document.getElementById("profile").appendChild(profileDropdownMenu);
	}
	else {
		document.getElementById("profile-dropdown-menu").remove();
	}
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
