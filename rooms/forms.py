from django import forms

from .models import Room


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "canvas_width", "canvas_height"]
        labels = {"canvas_width": "Canvas width", "canvas_height": "Canvas height"}
        help_texts = {"canvas_width": "In seat units: a seat is 80 wide and 44 tall."}

    def clean(self):
        data = super().clean()
        for field in ("canvas_width", "canvas_height"):
            if data.get(field) is not None and not 200 <= data[field] <= 4000:
                self.add_error(field, "Between 200 and 4000.")
        return data


class AddSeatsForm(forms.Form):
    count = forms.IntegerField(min_value=1, max_value=40, initial=1, label="Seats to add")
