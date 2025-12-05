function setTheme(theme) {
    const lightTheme = document.getElementById('light-theme');
    const darkTheme = document.getElementById('dark-theme');
    
    if (theme === 'dark') {
        lightTheme.disabled = true;
        darkTheme.disabled = false;
        document.body.setAttribute('theme', 'dark');
    } else {
        lightTheme.disabled = false;
        darkTheme.disabled = true;
        document.body.setAttribute('theme', 'light');
    }
}
document.addEventListener('DOMContentLoaded', (d)=>{
    var cookies = Object.fromEntries(document.cookie.split("; ").map(e => e.split("=")))
    var savedTheme = cookies["leetroute-theme"] || "light"; // Default to light
    let themeBtn = document.getElementById("theme-button");

    setTheme(savedTheme);
    themeBtn.setAttribute("state", savedTheme);
    document.cookie = `leetroute-theme=${savedTheme}; path=/`;
})

let themeBtn = document.getElementById("theme-button")
themeBtn.addEventListener("click", (e)=>{
    var btnState = e.currentTarget.getAttribute("state"); // Use currentTarget instead of target
    var newState = btnState === "dark" ? "light" : "dark";
    e.currentTarget.setAttribute("state", newState);
    setTheme(newState);
    document.cookie = `leetroute-theme=${newState}; path=/`;
});