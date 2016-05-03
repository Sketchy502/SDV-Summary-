function ajaxSuccess(data) {
    $('#recentFarms').empty();
    $.each(data, function(index, value){
        recentTemplate(value);
    });
};

function ajaxRequest(){
    $.getJSON('/_get_recents', {}, function(data){
        ajaxSuccess(data.recents);
    });
}

function recentTemplate(data){
    $('#recentFarms').append('<div class="col-md-4 col-sm-6 text-center previewbox"><a href="'+data[0]+'"><div class="previewimage"><img src="/static/images/'+data[0]+'/thumb.png" class="img-responsive farmimgpreview"><img src="/static/images/'+data[0]+'/avatar.png" class="headimg" ></div><div class="previewtext">'+data[1]+', '+data[2]+' Farm <br/>'+data[3]+'</div></a></div>');
}

$(document).ready(function(){
    var request = ajaxRequest;
    setInterval(ajaxRequest, 3000);
});