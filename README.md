# Saturdays

This repository contains the complete engineering architecture specification for Saturdays.

The repository consists of two parts.

## prompts/

Contains the governing documents.

These files define

- the role of the architect
- project constraints
- documentation standards
- workflow
- review process
- output structure
- generation rules

They are immutable.

## architecture/

This directory contains the generated engineering architecture.

Nothing inside this directory should violate the prompt documents.

The architecture should be generated incrementally.

Every document should pass review before the next document begins.