import React from "react";
import ReactDOM from "react-dom";
import Navigator from "./Navigator";

export class DiscoverCourses {
  constructor(context) {
    ReactDOM.render(<Navigator context={context} />, document.getElementById("root"));
  }
}

// Also assign directly to window for easier access
if (typeof window !== 'undefined') {
    window.DiscoverCourses = DiscoverCourses;
}
