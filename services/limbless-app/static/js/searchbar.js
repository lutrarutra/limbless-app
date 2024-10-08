
function select_option(name, id, search_field_id) {
    search_field_id = search_field_id.replace("-search", "");

    // Set value field value
    $(`#${search_field_id}`).val(id);

    // Set search field value
    $(`#${search_field_id}-search`).val(name);

    // Hide select results
    $(`#${search_field_id}-results`).css("display", "none");

    // Hide invalid feedback
    $(`#${search_field_id}-invalid-container`).empty();
    if ($(`#${search_field_id}-search`).hasClass("is-invalid")){
        $(`#${search_field_id}-search`).removeClass("is-invalid");
    }

    // Trigger htmx-change event for downstream components
    htmx.trigger(`#${search_field_id}`, "change");
}


// Hides search results when user clicks outside of search component
$(document).on("click", function(event) {
    if (!event.target.classList.contains("search-component")) {
        $(".search-select-results").css("display", "none");
    }
});