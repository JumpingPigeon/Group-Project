# 431W Web Programming Exercise

## Context
We used SQLite, Flask, and Python in this Assignment to create a web page that allows user to enter and delete patient names in its database. This is also a practice for using DBMS.

## Features
1. Provide a drop down menu that allows user to choose add/delete.
2. Auto generate a pid for new patient input.
3. Allow user to delete patient using First and Last Name.
4. Live update on patient data.
5. Prompt a window ask user to confirm their action before proceeding.

## Organization
* app.py for insert, delete, select, search, and handle redirect.
* templates store the html files
    * index.html is the main page
    * add_patient.html is use to add patient
    * delete_patient.html is use to remove patient

## Instructions
1. Open the code folder in VS code
2. Run **pip install flask**
3. Run **python app.py**
4. Click ***http://127.0.0.1:5000/*** in terminal

## Reference
1. HTML Tutorials:
   - Input Type Submit: https://www.w3schools.com/tags/att_input_type_submit.asp
   - HTML Tag Reference: https://www.w3schools.com/tags/
   - Select Tag: https://www.w3schools.com/tags/tag_select.asp
   - Form Method Attribute: https://www.w3schools.com/tags/att_form_method.asp
   - HTML Colors: https://www.w3schools.com/html/html_colors.asp

2. Flask Tutorials:
   - https://www.geeksforgeeks.org/python/redirecting-to-url-in-flask/
   - https://flask.palletsprojects.com/en/stable/tutorial/

3. SQL Tutorials:
   - https://www.w3schools.com/sql/sql_ref_insert_into.asp
   - https://www.w3schools.com/sql/sql_ref_delete.asp
   - Textbook Chapter 3

4. Bootstrap (Bonus Task):
   - https://getbootstrap.com/docs/4.0/components/modal/