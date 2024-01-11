function copyURLClipboard() {
    let urlLink = document.getElementById("copyURL");

    navigator.clipboard.writeText(urlLink.href)
        .then(() => submitButtonValidation(true))
        .catch(err => submitButtonValidation(false));
}


function submitButtonValidation(success) {
    let urlSubmit = document.getElementById("_url_submit_button");
    let urlSubmitOriginal = urlSubmit.innerText;

    if (!success) {
        // #d41010
        urlSubmit.style.color = "#d41010";
        urlSubmit.innerText = "Error!";
    }

    else {
        urlSubmit.innerText = "Copied!"; 
    }

    setTimeout(() => {
        urlSubmit.style.color = null;
        urlSubmit.innerText = urlSubmitOriginal;
    }, 2000);
}