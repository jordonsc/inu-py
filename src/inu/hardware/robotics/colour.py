from inu import error


class ColourCode:
    # Colour mappings courtesy of Copilot :)
    COLOUR_TABLE = {
        "BLACK": "#000000",
        "WHITE": "#FFFFFF",
        "RED": "#FF0000",
        "GREEN": "#00FF00",
        "BLUE": "#0000FF",
        "YELLOW": "#FFFF00",
        "CYAN": "#00FFFF",
        "MAGENTA": "#FF00FF",
        "SILVER": "#C0C0C0",
        "GRAY": "#808080",
        "MAROON": "#800000",
        "OLIVE": "#808000",
        "LIME": "#00FF00",
        "TEAL": "#008080",
        "AQUA": "#00FFFF",
        "NAVY": "#000080",
        "FUCHSIA": "#FF00FF",
        "PURPLE": "#800080",
        "ORANGE": "#FFA500",
        "BROWN": "#A52A2A",
        "TURQUOISE": "#40E0D0",
        "GOLD": "#FFD700",
        "PINK": "#FFC0CB",
        "VIOLET": "#EE82EE",
        "INDIGO": "#4B0082",
        "BEIGE": "#F5F5DC",
        "KHAKI": "#F0E68C",
        "TAN": "#D2B48C",
        "HONEYDEW": "#F0FFF0",
        "AZURE": "#F0FFFF",
        "LAVENDER": "#E6E6FA",
        "CORAL": "#FF7F50",
        "SALMON": "#FA8072",
        "TOMATO": "#FF6347",
        "ORCHID": "#DA70D6",
        "PERU": "#CD853F",
        "SEASHELL": "#FFF5EE",
        "CHOCOLATE": "#D2691E",
        "LINEN": "#FAF0E6",
    }

    def __init__(self, *args):
        """
        Create a colour code object from a hex or RGB string. The colour code may contain an optional 4th parameter
        which is the brightness.

        ex:
        ColourCode("#FF0000")  # Red
        ColourCode("255,0,0")  # Red
        ColourCode("#FF0000A0")  # Red, reduced brightness
        ColourCode("255,0,0,160")  # Red, reduced brightness
        ColourCode("RED")  # Red
        ColourCode(255, 0, 0, 255)  # Red

        :param col: Can be a colour name, an HTML-style hex code, or an RGB code.
        """
        self.r = 0
        self.g = 0
        self.b = 0
        self.x = 255

        if len(args) == 4:
            self.r, self.g, self.b, self.x = [ColourCode.check_bounds(int(part)) for part in args]
        elif len(args) == 1:
            col = str(args[0]).upper().strip()

            # Convert colour names to hex values
            if col in self.COLOUR_TABLE:
                col = self.COLOUR_TABLE[col]

            if col[0] == '#':
                # Hex code, HTML style
                self.decode_hex(col[1:])
            elif "," in col:
                # RGB (decimal) code
                self.decode_rgb(col)
            else:
                raise error.Malformed(f"Invalid colour code: {col}")
        else:
            raise error.Malformed("Invalid number of arguments")

    def decode_hex(self, col: str):
        if len(col) != 6 and len(col) != 8:
            raise error.Malformed("Invalid hex color code")

        self.r, self.g, self.b = [int(col[i:i + 2], 16) for i in range(0, 6, 2)]
        self.x = int(col[6:8], 16) if len(col) == 8 else 255

    def decode_rgb(self, col: str):
        parts = col.split(",")

        if len(parts) < 3 or len(parts) > 4:
            raise error.Malformed("Invalid RGB color code")

        self.r, self.g, self.b = [ColourCode.check_bounds(int(part.strip())) for part in parts[:3]]
        self.x = ColourCode.check_bounds(int(parts[3].strip())) if len(parts) == 4 else 255

    def unpack(self):
        return self.r, self.g, self.b, self.x

    @staticmethod
    def check_bounds(value):
        if 0 <= value <= 255:
            return value
        else:
            raise error.Malformed("RGB values must be between 0 and 255 inclusive")

    def __repr__(self):
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}{self.x:02x}"
