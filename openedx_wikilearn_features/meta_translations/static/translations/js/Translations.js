import React from "react";
import ReactDOM from "react-dom";
import TranslationContent from "./TranslationContent";
import "react-toastify/dist/ReactToastify.css";

export class Translations {
  constructor(context) {
    ReactDOM.render(<TranslationContent context={context} />, document.getElementById("root"));
  }
}

// Also assign directly to window for easier access
if (typeof window !== 'undefined') {
    window.Translations = Translations;
}
