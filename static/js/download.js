// {
// 	"title": "Flushed Away",
// 	"page_url": "https://gomovies-online.cam/watch-film/flushed-away/6N8p178f",
// 	"poster_url": "https://static.gomovies-online.cam/dist/img/UI8PAe7IzXTeCQl4aF9SqFxc5YsWt9wHRD2UgAy3culxFUdWsD5ckp32IfKlMqWNZmsCMpsk2sffXG_NWWAfaWQkhVjoB4hR32MXmEumXW0.jpg",
// 	"data": {
// 		"title": "Flushed Away",
// 		"release_year": "2006",
// 		"imdb_score": "IMDb: 6.6",
// 		"duration": "85 min",
// 		"release_country": "United States, United Kingdom",
// 		"genre": "Comedy, Adventure, Animation",
// 		"description_preview": "After an ignoble landing in Ratropolis, a pampered rodent\xa0that gets flushed down the toilet from his penthouse apartment\xa0enlists the help of a...",
// 		"key": "0",
// 		"quality_tag": "HD",
// 		"user_rating": "5.000000"
// 	}
// }

// onItemClick = function (result) {
// 	// encode result to be url safe
// 	result = encodeURIComponent(JSON.stringify(result));
// 	console.log(result);
// 	httpPostAsync(API_HOST +":"+ API_PORT +"/api/v2/download?result="+ result, handleDownloadResponse);
// };

function removeAllChildNodes(parent) {
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}

function stopCardSpinner(id) {
	var result = document.getElementById("id-"+ id);
	var result_thumbnail = result.getElementsByClassName("result-thumbnail")[0];
	if (result.lastChild.tagName == "DIV")
		removeAllChildNodes(result.lastChild);
}

handleDownloadResponse = function (response) {
	// response = JSON.parse(response.responseText);
	const json = JSON.parse(response.responseText);
	stopCardSpinner(json.id);
	// Response is 200 or 201
	if ([200, 201].includes(response.status)) {
		console.log(json.message);
		console.log(json.video_data);
		console.log(json.id);
		startCardSpinner(json.id, "/static/img/check.svg");
	} else if ([400, 500, 508].includes(response.status)) {
		console.log(json.message);
		console.log(json.video_data);
		console.log(json.id);
		startCardSpinner(json.id, "/static/img/error.svg");
	}
	// if (response.status == 225) {
	// 	const captchaImage = json.data;
	// 	const page_url = json.page_url;
	// 	console.log("HTTP response status code: "+ response.status +"\n"+ json.message);
	// 	captchaPopUp(captchaImage, page_url);
	// }
};
