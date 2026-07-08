import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import CourseTranslations from "./components/CourseTranslations";
import DiscoverCoursesContent from "./components/DiscoverCoursesContent";

export default function Navigator({ context }) {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/meta_translations/discover_courses/" element={<DiscoverCoursesContent context={context} />} />
        <Route path="/meta_translations/discover_courses/:course_id" element={<CourseTranslations context={context} />} />
      </Routes>
    </BrowserRouter>
  );
}
