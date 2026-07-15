class StyleAdapter:
    def choose_style(self, preferred_style: str, feedback_useful: bool | None) -> str:
        if feedback_useful is False:
            if preferred_style == "visual":
                return "hands-on"
            if preferred_style == "hands-on":
                return "story"
            return "visual"
        return preferred_style
