import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Grid, SampleOwner
from .permissions import visible_owners
from .preparation import PREPARATION_FIELDS, PREPARATION_GROUPS, compact_decimal
from .services import validate_preparation


class CompactNumberInput(forms.NumberInput):
    def format_value(self, value):
        return super().format_value(compact_decimal(value))


class PreparationForm(forms.ModelForm):
    multiple_blot = forms.IntegerField(
        label="Multiple blots",
        required=False,
        min_value=0,
        initial=0,
        help_text="Defaults to 0. Enter a whole number, 0 or greater.",
        widget=forms.NumberInput(attrs={"min": 0, "step": 1}),
    )

    class Meta:
        model = Grid
        fields = PREPARATION_FIELDS
        widgets = {
            "sample_concentration_value": CompactNumberInput(),
            "sample_description": forms.Textarea(attrs={"rows": 2}),
            "buffer_description": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "glow_device": forms.TextInput(attrs={"placeholder": "Unknown"}),
            "freezing_device": forms.TextInput(attrs={"placeholder": "Unknown"}),
        }
        labels = {
            "sample_concentration_value": "Concentration",
            "sample_concentration_unit": "Concentration unit (e.g. mg/mL)",
            "carbon_thickness_nm": "Carbon thickness (nm)",
            "carbon_thickness_layers": "Carbon thickness (layers)",
            "carbon_description": "Additional carbon",
            "glow_device": "Device",
            "freezing_device": "Device",
            "glow_current_ma": "Glow current (mA)",
            "glow_duration_s": "Glow duration (s)",
            "sample_volume_ul": "Sample volume (µL)",
            "temperature_c": "Temperature (°C)",
            "humidity_percent": "Relative humidity (%)",
            "blot_time_s": "Blot time (s)",
            "hold_time_s": "Hold time (s)",
            "drain_time_s": "Drain time (s)",
            "blot_force": "Blot force (instrument scale)",
            "multiple_blot": "Multiple blots",
            "grid_box_number": "Batch (Box/LOT-number)",
        }

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            try:
                validate_preparation(self.preparation_values())
            except ValidationError as error:
                self.add_error(None, error)
        return cleaned

    def clean_multiple_blot(self):
        value = self.cleaned_data.get("multiple_blot")
        return 0 if value is None else value

    def preparation_values(self):
        return {
            name: self.cleaned_data[name]
            for name in PREPARATION_FIELDS
            if name in self.cleaned_data
        }

    def preparation_groups(self):
        return [(title, [self[name] for name in names]) for title, names in PREPARATION_GROUPS]


class NewSessionForm(PreparationForm):
    owner = forms.ModelChoiceField(queryset=SampleOwner.objects.none(), label="Sample owner")
    prepared_at = forms.DateTimeField(
        label="Preparation date and time",
        initial=timezone.now,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        help_text="Local time in Europe/Stockholm. Enter when the preparation happened.",
    )
    experiment_reference = forms.CharField(required=False, max_length=200)
    project_reference = forms.CharField(required=False, max_length=200)
    session_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    grid_count = forms.IntegerField(min_value=1, max_value=100, initial=8, label="Number of grids")
    request_token = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = visible_owners(actor).filter(active=True)
        self.fields["glow_device"].initial = "Quorum – GloCube+"
        self.fields["freezing_device"].initial = "Vitrobot Mark IV"


class EditGridForm(PreparationForm):
    expected_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)


class OwnerNameForm(forms.Form):
    name = forms.CharField(max_length=200, label="Sample owner name")


class OwnerRegistrationForm(forms.ModelForm):
    owner_code_preview = forms.CharField(required=False, max_length=40)

    class Meta:
        model = SampleOwner
        fields = ["name", "affiliation", "notes"]
        labels = {"name": "Sample owner name"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class AdminOwnerForm(forms.ModelForm):
    # Display only: the service always allocates the real code on save. A posted
    # preview value must never be trusted as an assigned identifier.
    owner_code_preview = forms.CharField(
        label="Unique owner code",
        required=False,
        widget=forms.TextInput(attrs={"readonly": True}),
        help_text="Four lowercase letters/digits based on the name. Fixed after registration.",
    )

    class Meta:
        model = SampleOwner
        fields = ["name", "affiliation", "notes", "active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner_code_preview"].initial = self.instance.code
        self.fields["name"].widget.attrs["data-code-creating"] = (
            "true" if self.instance._state.adding else "false"
        )


class SessionBrowseForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=200,
        label="Search sessions",
        help_text="Session number, owner, operator, experiment or project.",
    )
    owner = forms.ModelChoiceField(
        queryset=SampleOwner.objects.none(), required=False, empty_label="All owners"
    )
    from_date = forms.DateField(
        required=False, label="Prepared from", widget=forms.DateInput(attrs={"type": "date"})
    )
    to_date = forms.DateField(
        required=False, label="Prepared through", widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = visible_owners(actor)

    def clean(self):
        data = super().clean()
        start, finish = data.get("from_date"), data.get("to_date")
        if start and finish and start > finish:
            raise forms.ValidationError("The start date must not be after the end date.")
        return data


class DeleteGridForm(forms.Form):
    password = forms.CharField(
        label="Your password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    expected_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)


class DeletedGridBrowseForm(forms.Form):
    q = forms.CharField(required=False, max_length=200, label="Search deleted grids")
    session = forms.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807, label="Session number"
    )


class ExcelImportForm(forms.Form):
    workbook = forms.FileField(
        label="Registry Excel workbook",
        widget=forms.FileInput(attrs={"accept": ".xlsx"}),
        help_text="Upload a current registry export (.xlsx, at most 5 MB).",
    )
