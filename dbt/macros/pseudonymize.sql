{# Pseudonimiseer een kolom met SHA-256 + zout.

   Production zou een per-cliënt-zout en HSM-gestuurde re-identificatie-service
   gebruiken; voor referentie volstaat een statische zout uit env-var.

   Gebruik in een SELECT:
     {{ pseudonymize('bsn') }} AS bsn_pseudo
#}
{% macro pseudonymize(column, salt=none) %}
    {%- set _salt = salt if salt is not none else var('pseudonymize_salt') -%}
    to_hex(sha256(to_utf8(concat(cast({{ column }} as varchar), '{{ _salt }}'))))
{% endmacro %}
