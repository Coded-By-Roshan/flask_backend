from io import BytesIO
import threading
import shutil
from google.cloud import firestore
from datetime import datetime
import cv2
import time
from flask import Flask, render_template, request, jsonify, Response
from PIL import Image
import io
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, jsonify, send_file
from fpdf import FPDF
import os
import firebase_admin
from firebase_admin import credentials, firestore
import operator
0
# Firebase@123
# Provide the path to the service account key file
cred = credentials.Certificate(
    'omr-master-project-firebase-adminsdk-sbakz-bcc3da7e2c.json'
)

firebase_admin.initialize_app(
    cred,
    {
        "projectId": "omr-master-project",
    },
)

db = firestore.client()
#  very inportant step to set up stuff


class OMR:
    def __init__(self, roll_number_digits, number_of_exam_set, number_of_subjects):
        self.roll_number_digits = roll_number_digits
        self.number_of_exam_set = number_of_exam_set
        self.number_of_subjects = number_of_subjects + 2
        self.subjects = []

    def add_subject(self, subject):
        self.subjects.append(subject)

class Subject:
    def __init__(self, name, number_of_sections):
        self.name = name
        self.number_of_sections = number_of_sections
        self.sections = []

    def add_section(self, section):
        self.sections.append(section)

class Section:
    def __init__(
        self,
        number_of_questions,
        number_of_options,
        question_type,
        section_heading,
        height_of_section,
    ):
        self.section_heading = section_heading
        self.question_type = question_type
        self.number_of_questions = number_of_questions
        self.number_of_options = number_of_options
        self.decimal_position = None
        self.number_of_options_drawn = []
        self.section_height = height_of_section


def convert_to_2d_array(file_path):
    array_2d = []
    with open(file_path, "r") as file:
        for line in file:
            # print(line)
            line = line.strip()  # Remove leading/trailing whitespace
            array = [str(char) for char in line]  # Convert each character to integer
            array_2d.append(array)
    file.close()
    return array_2d

# final = convert_to_2d_array(
#     "final_answer_key.txt"
# )

def create_omr_sheet2(file_path, freq, num_circle):
    with open(file_path, "r") as f:
        lines = f.read().splitlines()  # read all lines from the file
    i = 0  # initialize a counter for line number

    roll_number_digits = int(lines[i])
    i += 1

    number_of_exam_set = int(lines[i])
    i += 1

    number_of_subjects = int(lines[i])
    i += 1

    omr_sheet = OMR(roll_number_digits, number_of_exam_set, number_of_subjects)

    for _ in range(number_of_subjects):
        subject_name = lines[i]
        # labels_of_all_headings.append(subject_name)
        # type_of_all_headings.append(0)
        i += 1

        number_of_sections = int(lines[i])
        i += 1

        subject = Subject(subject_name, number_of_sections)

        for _ in range(number_of_sections):
            # labels_of_all_headings.append(lines[i])
            section_heading = lines[i]
            i += 1

            number_of_questions = int(lines[i])
            freq.append(number_of_questions)
            i += 1

            number_of_options = int(lines[i])
            num_circle.append(number_of_options)
            i += 1

            question_type = lines[i]

            i += 1
            
            height_of_section = 0
            section = Section(
                number_of_questions,
                number_of_options,
                question_type,
                section_heading,
                height_of_section,
            )
            subject.add_section(section)

        omr_sheet.add_subject(subject)

    return omr_sheet, freq, num_circle

def merge_images(images):
    widths, heights = zip(*(i.size for i in images))
    widths, heights = zip(*(i.size for i in images))
    total_width = max(widths)
    max_height = sum(heights)
    new_img = Image.new("RGB", (total_width, max_height))
    y_offset = 0
    for img in images:
        new_img.paste(img, (0, y_offset))
        y_offset += img.height
    return new_img


page = 0
circle_diameter = 60
gap_between_circles = 30
border_width = 5
default_section_gap = 25
font_size = 50
line_gap = 25
numbering_gap = 80
tf_gap_multiplier = 3
label_gap = 25
page_limit = 15000
widths = [0, 0, 0, 0]


def writing(draw, content, height, width, gap_from_left):
    # write the content on the omr sheet
    text_bbox = draw.textbbox((0, 0), content)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (width - text_width) / 2
    draw.text((text_x, height), content, fill="black")
    height += text_height + line_gap
    return height


def bubble_draw(
    img,
    page,
    draw,
    number_of_questions,
    number_of_options,
    question_type,
    height,
    width,
    gap_from_left,
    gap_between_circles,
    circle_diameter,
    border_width,
    tf_gap_multiplier,
    decimal_font,
    decimal_position,
    number_font,
    font_size,
    label_gap,
    default_section_gap,
    line_gap,
    starting_row,
    real_pages,
):
    columns = number_of_options
    rows = number_of_questions
    row_label = ""
    if question_type == "MCQ":
        row_label = str(starting_row + 1)
        for col in range(columns):
            alphabetical_label = chr(ord("A") + col)
            text_bbox = draw.textbbox((0, 0), alphabetical_label, font=number_font)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(
                (
                    col * (circle_diameter + gap_between_circles)
                    + gap_between_circles
                    + gap_from_left
                    + (circle_diameter - text_width) / 2,
                    height - default_section_gap - label_gap,
                ),
                alphabetical_label,
                fill="black",
                font=number_font,
            )
    elif question_type == "matrix":
        row_label = chr(ord("P"))
        for col in range(columns):
            alphabetical_label = chr(ord("P") + col)
            text_bbox = draw.textbbox((0, 0), alphabetical_label, font=number_font)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(
                (
                    col * (circle_diameter + gap_between_circles)
                    + gap_between_circles
                    + gap_from_left
                    + (circle_diameter - text_width) / 2,
                    height - default_section_gap - label_gap,
                ),
                alphabetical_label,
                fill="black",
                font=number_font,
            )
    elif question_type == "num" or question_type == "deci":
        row_label = str(0)
        for col in range(columns):
            alphabetical_label = "□"
            if decimal_position == col:
                alphabetical_label = "."
            text_bbox = draw.textbbox((0, 0), alphabetical_label, font=decimal_font)
            decimal_font_2 = ImageFont.truetype("arial.ttf", int(font_size*2))
            text_width = text_bbox[2] - text_bbox[0] + -100
            draw.text(
                (
                    col * (circle_diameter + gap_between_circles)
                    + gap_between_circles
                    + gap_from_left
                    + (circle_diameter - text_width) / 2,
                    height - default_section_gap - label_gap - 50,
                ),
                alphabetical_label,
                fill="black",
                font=decimal_font_2,
            )
    elif question_type == "TF":
        row_label = str(1)
        for col in range(columns):
            alphabetical_label = "       T"
            text_bbox = draw.textbbox((0, 0), alphabetical_label, font=number_font)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(
                (
                    (circle_diameter + gap_between_circles - text_width) / 2
                    + gap_from_left,
                    height - default_section_gap - label_gap,
                ),
                alphabetical_label,
                fill="black",
                font=number_font,
            )
            alphabetical_label = "        F"
            text_bbox = draw.textbbox((0, 0), alphabetical_label, font=number_font)
            text_width = text_bbox[2] - text_bbox[0]
            draw.text(
                (
                    (circle_diameter + gap_between_circles - text_width) / 2
                    + gap_between_circles
                    + circle_diameter
                    + gap_from_left,
                    height - default_section_gap - label_gap,
                ),
                alphabetical_label,
                fill="black",
                font=number_font,
            )

    temp_height = height
    for row in range(rows - starting_row):
        if height + circle_diameter + gap_between_circles > 3100 * (real_pages + 1):
            real_pages += 1
            height += 3100 - (height) % 3100
        text_bbox = draw.textbbox((0, 0), row_label, font=number_font)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(
            (
                gap_from_left - text_width - gap_between_circles,
                height + gap_between_circles + (circle_diameter - font_size) / 2,
            ),
            row_label,
            fill="black",
            font=number_font,
        )
        for col in range(columns):
            if question_type == "deci":
                if decimal_position == col:
                    upper_left = (
                        col * (circle_diameter + gap_between_circles)
                        + gap_between_circles
                        + gap_from_left,
                        height
                        + (circle_diameter + gap_between_circles)
                        + gap_between_circles,
                    )
                    lower_right = (
                        (col + 1) * (circle_diameter + gap_between_circles)
                        + gap_from_left,
                        height + (1) * (circle_diameter + gap_between_circles),
                    )
                    draw.ellipse(
                        [upper_left, lower_right], outline="white", width=border_width
                    )
                    continue
            # if question type tf then the distance between two bubbles is 3 times the normal distance

            upper_left = (
                col * (circle_diameter + gap_between_circles)
                + gap_between_circles
                + gap_from_left,
                height + gap_between_circles,
            )
            lower_right = (
                (col + 1) * (circle_diameter + gap_between_circles) + gap_from_left,
                height + (1) * (circle_diameter + gap_between_circles),
            )
            draw.ellipse([upper_left, lower_right], outline="black", width=border_width)
        row_label = str(int(row_label) + 1)
        temp_height += circle_diameter + gap_between_circles
        height += circle_diameter + gap_between_circles

    return height, draw, page, img, True, row, real_pages


def split_image(img, column_images, height_split):
    # Open the image file.
    # img = Image.open(image_path)
    width, height = img.size

    # Make sure the height_split value is valid.
    # if height_split > height:
    #     print("The split size is greater than the height of the image.")
    #     return

    # Calculate the number of chunks to split the image into.
    num_chunks = height // height_split
    if height % height_split != 0:
        num_chunks += 1

    # Split the image.
    for i in range(num_chunks):
        top = i * height_split
        bottom = (i + 1) * height_split if (i + 1) * height_split < height else height
        new_img = img.crop((0, top, width, bottom))
        column_images.append(new_img)
        # new_img.save(output_path + str(i) + ".png")
    return column_images

app = Flask(__name__)

def add_data_database(request_data):
    print("here")
    index = 0
    exams_ref = db.collection("Exams")
    subject_ref = db.collection("Subjects")
    section_ref = db.collection("Sections")
    roll_number_digits = request_data["roll_number_digits"]
    number_of_exam_set = request_data["number_of_exam_set"]
    number_of_subjects = request_data["number_of_subjects"]
    name_of_exam = request_data["name_of_exam"]
    admin_email = request_data["admin_email"]
    # in ddmmyyyy format from time library
    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%d/%m/%Y")

    exams_ref.add(
        {
            "Exam_Sets": number_of_exam_set,
            "Exam_Name": name_of_exam,
            "Roll_Number_Digits": roll_number_digits,
            "Number_of_Subjects": number_of_subjects,
            "Admin_Email":  admin_email,
            "Creation_Date" : formatted_datetime,
        }
    )
    for subject_data in request_data["subjects"]:
        subject_name = subject_data["name"]
        number_of_sections = subject_data["number_of_sections"]
        # subject = Subject(subject_name, number_of_sections)
        subject_ref.add(
            {
                "Admin_Email": admin_email,
                "Exam_Name": name_of_exam,
                "Number_of_Sections": number_of_sections,
                "Subject_Name": subject_name,
                "index": index,
            }
        )
        index += 1
        for section_data in subject_data["sections"]:
            section_heading = section_data["section_heading"]
            number_of_questions = section_data["number_of_questions"]
            number_of_options = section_data["number_of_options"]
            question_type = section_data["question_type"]
            height_of_section = section_data["height_of_section"]

            section_ref.add(
                {
                    "Admin_Email": admin_email,
                    "Decimal_Position": 0,
                    # "Height of Section": height_of_section,
                    "Exam_Name": name_of_exam,
                    "Options": number_of_options,
                    "Question_Type": question_type,
                    "Questions": number_of_questions,
                    "Section_Heading": section_heading,
                    "Subject_Name": subject_name,
                    "index": index,
                }
            )
            index += 1
            section = Section(
                number_of_questions,
                number_of_options,
                question_type,
                section_heading,
                height_of_section,
            )
            print(height_of_section)
            # subject.add_section(section)

        # omr_sheet.add_subject(subject)


@app.route("/create_omr_sheet", methods=["POST"])
def create_omr_sheet_endpoint():

    print(time.time())
    # print("create_omr_sheet_endpoint")
    # here I will reference to all the data that needs to be stored in the database
    request_data = request.json
    
    thread = threading.Thread(target=add_data_database, args=(request_data,))
    thread.start()
    # add_data_database(request_data)
    index = 0

    print("request_data", request_data)
    
    print(1)
    print(time.time())
    
    roll_number_digits = request_data["roll_number_digits"]
    number_of_exam_set = request_data["number_of_exam_set"]
    number_of_subjects = request_data["number_of_subjects"]
    name_of_exam = request_data["name_of_exam"]
    admin_email = request_data["admin_email"]
    
    omr_sheet = OMR(roll_number_digits, number_of_exam_set, number_of_subjects)
    subject = Subject("Roll Number", 1)
    section = Section(
                10,
                roll_number_digits,
                "num",
                " ",
                0,
            )
    subject.add_section(section)
    omr_sheet.add_subject(subject)
    subject = Subject("Exam Set", 1)
    section = Section(
                1,
                number_of_exam_set,
                "MCQ",
                "   ",
                0,
            )
    subject.add_section(section)
    omr_sheet.add_subject(subject)

    for subject_data in request_data["subjects"]:
        subject_name = subject_data["name"]
        number_of_sections = subject_data["number_of_sections"]
        subject = Subject(subject_name, number_of_sections)
        # subject_ref.add(
        #     {
        #         "Admin_Email": admin_email,
        #         "Exam_Name": name_of_exam,
        #         "Number_of_Sections": number_of_sections,
        #         "Subject_Name": subject_name,
        #         "index": index,
        #     }
        # )
        index += 1
        for section_data in subject_data["sections"]:
            section_heading = section_data["section_heading"]
            number_of_questions = section_data["number_of_questions"]
            number_of_options = section_data["number_of_options"]
            question_type = section_data["question_type"]
            height_of_section = section_data["height_of_section"]

            # section_ref.add(
            #     {
            #         "Admin_Email": admin_email,
            #         "Decimal_Position": 0,
            #         # "Height of Section": height_of_section,
            #         "Exam_Name": name_of_exam,
            #         "Options": number_of_options,
            #         "Question_Type": question_type,
            #         "Questions": number_of_questions,
            #         "Section_Heading": section_heading,
            #         "Subject_Name": subject_name,
            #         "index": index,
            #     }
            # )
            index += 1
            section = Section(
                number_of_questions,
                number_of_options,
                question_type,
                section_heading,
                height_of_section,
            )
            print(height_of_section)
            subject.add_section(section)

        omr_sheet.add_subject(subject)

    omr = omr_sheet
    
    print(2)
    print(time.time())

    path = "column"
    # width = 560
    # height = 3100   
    # color = (255, 255, 255)  # RGB value for white
    # for i in range(0,4):
    #     img = Image.new('RGB', (width, height), color)
    #     img.save(path + str(i) + ".png")

    page = 0
    circle_diameter = 57
    gap_between_circles = 30
    border_width = 5
    default_section_gap = 20
    font_size = 55
    line_gap = 20
    numbering_gap = 70
    tf_gap_multiplier = 3
    label_gap = 20
    page_limit = 15000
    widths = [0, 0, 0, 0]

    labels_of_all_headings = []
    type_of_all_headings = []  # 0 for multi tf, 1 for matrix, deci num
    sections_at_those_heights = []
    real_pages = 0

    first_width = (
        omr.roll_number_digits * (circle_diameter + gap_between_circles)
        + gap_between_circles
        + numbering_gap
    )
    img = Image.new("RGB", (560, page_limit + page_limit % 3100), "white") # experiment 560
    # img = Image.new("RGB", (first_width + 100, page_limit + page_limit % 3100), "white")
    draw = ImageDraw.Draw(img)
    print(3)
    print(time.time())
    y_offset = label_gap
    count = 0
    max_height = 0
    section = 0
    temp_hight = y_offset
    for i in range(omr.number_of_subjects):
        print("printed name of subject", omr.subjects[i].name)

        temp_hight += font_size + line_gap + default_section_gap + label_gap
        for j in range(omr.subjects[i].number_of_sections):
            print(
                "printed name of section", omr.subjects[i].sections[j].section_heading
            )
            widths[page] = max(
                widths[page],
                omr.subjects[i].sections[j].number_of_options
                * (circle_diameter + gap_between_circles)
                + gap_between_circles
                + numbering_gap,
            )

            temp_hight += font_size + line_gap + default_section_gap + label_gap
            decimal_position = omr.subjects[i].sections[j].decimal_position
            temp_hight += gap_between_circles + (default_section_gap + label_gap)
            for k in range(omr.subjects[i].sections[j].number_of_questions):
                print("printed question number", k)
                widths[page] = max(
                    widths[page],
                    omr.subjects[i].sections[j].number_of_options
                    * (circle_diameter + gap_between_circles)
                    + gap_between_circles
                    + numbering_gap,
                )
                temp_hight += circle_diameter + gap_between_circles

    print("here page number is " + str(page))
    page = 0

    heights_of_headings = []
    print(4)
    print(time.time())
    # y_offset = (
    #             writing(
    #                 draw,
    #                 "Name: _____________",
    #                 y_offset,
    #                 widths[page],
    #                 numbering_gap,
    #             )
    #             + default_section_gap
    #             + label_gap
    #         )
    # y_offset = (
    #             writing(
    #                 draw,
    #                 "Class: _____________",
    #                 y_offset,
    #                 widths[page],
    #                 numbering_gap,
    #             )
    #             + default_section_gap
    #             + label_gap
    #         )
    for i in range(omr.number_of_subjects):
        # heights_of_headings.append(y_offset)
        # sections_at_those_heights.append(omr.subjects[i])
        if (
            omr.subjects[i].sections[0].question_type == "deci"
            or omr.subjects[i].sections[0].question_type == "num"
            or omr.subjects[i].sections[0].question_type == "matrix"
        ):
            if (y_offset + 1500) > 3100 * (real_pages + 1):
                y_offset += 3100 - (y_offset) % 3100
                real_pages += 1
                print("here1")
        y_offset = writing(
            draw, omr.subjects[i].name, y_offset, widths[page], numbering_gap
        )
        for j in range(omr.subjects[i].number_of_sections):
            if (
                omr.subjects[i].sections[j].question_type == "deci"
                or omr.subjects[i].sections[j].question_type == "num"
                or omr.subjects[i].sections[j].question_type == "matrix"
            ):
                if (y_offset + 1380) > 3100 * (real_pages + 1):
                    print("here2")
                    real_pages += 1
                    y_offset += 3100 - (y_offset) % 3100

            y_offset = (
                writing(
                    draw,
                    omr.subjects[i].sections[j].section_heading,
                    y_offset,
                    widths[page],
                    numbering_gap,
                )
                + default_section_gap
                + label_gap
            )
            decimal_position = omr.subjects[i].sections[j].decimal_position
            flag = False
            rowing = 0
            y_offset, draw, page, img, flag, rowing, real_pages = bubble_draw(
                img,
                page,
                draw,
                omr.subjects[i].sections[j].number_of_questions,
                omr.subjects[i].sections[j].number_of_options,
                omr.subjects[i].sections[j].question_type,
                y_offset,
                widths[0],
                numbering_gap,
                gap_between_circles,
                circle_diameter,
                border_width,
                tf_gap_multiplier,
                decimal_position,
                font_size,
                label_gap,
                default_section_gap,
                line_gap,
                rowing,
                real_pages,
            )
            y_offset += default_section_gap + label_gap
            widths[page] = max(
                widths[page],
                omr.subjects[i].sections[j].number_of_options
                * (circle_diameter + gap_between_circles)
                + gap_between_circles
                + numbering_gap,
            )

    # img = img.crop((0, 0, widths[page], y_offset)) experiment
    print(5)
    print(time.time())
    img = img.crop((0, 0, 560, y_offset))
    # img.save(path + str(page) + ".png")
    column_images = []
    column_images = split_image(img, column_images, 3100)

    print(6)
    print(time.time())

    path = "omr_sheet_full.png"
    # image_filenames = ["column0.png", "column1.png", "column2.png", "column3.png"]
    # for i in image_filenames:
    #     source_path = i
    #     destination_path = i[:-4] + "copy.png"
    #     shutil.copy(source_path, destination_path)

    # image_path2 = (
    #     "take_away_marekrs_new.jpg"
    # )
    # pasting = Image.open(image_path2)
    # new_image = Image.open(path)
    # new_image.paste(pasting, (25, 350))
    # new_image.paste(pasting, (2480-75, 350))
    # new_image.save("omr_sheet_full.png")

    # save new_image



    
    # image_path = ""
    # image_objects = [
    #     Image.open(os.path.join(image_path, img)) for img in image_filenames
    # ]
    paste_coords = [100]
    # for i in range(1, len(image_objects)):
    for i in range(1, len(column_images)):
        paste_coords.append(paste_coords[i - 1] + column_images[i - 1].width + 20)
    new_image = Image.open(path)
    # new_image.paste(pasting, (25, 350))
    print(7)
    print(time.time())
    for img, coord in zip(column_images, paste_coords):
        new_image.paste(img, (coord, 350))

    # new_image.paste(pasting, (2480-75, 350))
    # new_image.save("final.png")
    new_image2 = io.BytesIO()
    print(8)
    print(time.time())
    new_image.save(new_image2, format="PNG")
    new_image2.seek(0)
    print(9)
    print(time.time())
    # save the imgae in the local folder
    new_image.save("final.png")
    return send_file(new_image2, mimetype="image/png")

from flask import Flask, render_template, request, jsonify
import cv2

def order_points(pts):
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype="float32")

    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # return the ordered coordinates
    return rect

def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them
    # individually
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordinates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array(
        [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
        dtype="float32",
    )

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    # return the warped image
    return warped

import numpy as np
import imutils
import numpy as np

def give_correct_image_orientation(image):
    ratio = image.shape[0] / 500.0
    orig = image.copy()
    image = imutils.resize(image, height=500)

    # Convert image to grayscale and blur it
    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grayscale = cv2.GaussianBlur(grayscale, (5, 5), 0)

    # Find edges in the image
    edged = cv2.Canny(grayscale, 75, 200)

    # Find contours in the edged image
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    # Continue from the loop over the contours

    # Initialize screenCnt
    screenCnt = None

    for contour in contours:
        # Approximate the contour
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        # If our approximated contour has four points, then we
        # can assume that we have found our paper
        if len(approx) == 4:
            screenCnt = approx
            break

    # If we found a contour with four points, proceed
    if screenCnt is not None:
        # Apply the four point transform to obtain a top-down view of the original image
        warped = four_point_transform(orig, screenCnt.reshape(4, 2) * ratio)

        # Save the cropped image
        cv2.imwrite(
            "scanned2.jpg", warped
        )
        image = cv2.imread(
            "scanned2.jpg"
        )
        return "Success"
    else:
        return "No contour found with four points. Unable to scan document."

def resize_image(input_image_path, output_image_path, new_width, new_height):
    original_image = Image.open(input_image_path)
    resized_image = original_image.resize((new_width, new_height))
    resized_image.save(output_image_path)


def extract_roll(roll):
    matrix = []
    #  roll is of length 50 convert it into a matrix of 5 columns and 10 rows
    for i in range(0, 50, 5):
        matrix.append(roll[i : i + 5])
    num_columns = len(matrix[0])
    roll_numebr = 0
    for col in range(num_columns):
        column_numbers = [matrix[row][col] for row in range(len(matrix))]
        column_string = ''.join(str(number) for number in column_numbers)
        print(column_string)
        for i in range(0, 10):
            if column_string[i] == '1':
                roll_numebr = roll_numebr * 10 + i
    return roll_numebr


@app.route("/receive_omr_sheet", methods=["POST"])
def receive_omr_sheet():
    tt = time.time()
    time_start = time.time()
    results_ref = db.collection("Results")
    if "image" not in request.files:
        return jsonify({"message": "No image in request"}), 400
    viewfinder_image = request.files["image"]

    name_of_exam = request.form["examName"]
    admin_email = request.form["adminEmail"]
    image = Image.open(BytesIO(viewfinder_image.read()))

    # print(name_of_exam, admin_email)
    # viewfinder_image_path = (
    #     "testing_scan.jpg"
    # )#change this file to the one that is received from the app
    # viewfinder_image.save(viewfinder_image_path)
    # image = Image.open(viewfinder_image_path)


    # response_from_orientation = give_correct_image_orientation(image)
    time_end = time.time()
    print("time taken to get image from app", time_end - time_start)
    time_start = time.time()
    print(name_of_exam, admin_email)
    freq = []
    num_circle = []

    # Get Exam data from Firestore
    exams_ref = db.collection('Exams')
    query_ref = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
    exams_docs = query_ref.stream()

    for exam_doc in exams_docs:
        exam_data = exam_doc.to_dict()

        # Create OMR object
        roll_number_digits = exam_data.get('Roll_Number_Digits', None)
        exam_sets = exam_data.get('Exam_Sets', None)
        num_subjects = exam_data.get('Number_of_Subjects', None)
        omr = OMR(roll_number_digits, exam_sets, num_subjects)
        freq.append(10)
        freq.append(1)
        num_circle.append(5)
        num_circle.append(3)
        # Get Subjects data from Firestore
        subjects_ref = db.collection('Subjects')
        query_ref = subjects_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
        subjects_docs = query_ref.stream()

        # Store all subjects in a list
        subjects_list = []
        for subject_doc in subjects_docs:
            subject_data = subject_doc.to_dict()
            num_sections = subject_data.get('Number_of_Sections', None)
            subject_name = subject_data.get('Subject_Name', None)
            subject = Subject(subject_name, num_sections)
            subjects_list.append((subject_data['index'], subject))

        # Sort subjects based on index and add to OMR
        subjects_list.sort(key=operator.itemgetter(0))
        for index, subject in subjects_list:
            omr.add_subject(subject)

            # Get Sections data from Firestore
            sections_ref = db.collection('Sections')
            query_ref = sections_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam).where('Subject_Name', '==', subject.name)
            sections_docs = query_ref.stream()

            # Store all sections in a list
            sections_list = []
            for section_doc in sections_docs:
                section_data = section_doc.to_dict()
                num_questions = section_data.get('Questions', None)
                num_options = section_data.get('Options', None)
                question_type = section_data.get('Question_Type', None)
                section_heading = section_data.get('Section_Heading', None)
                section = Section(num_questions, num_options, question_type, section_heading, 0)
                sections_list.append((section_data['index'], section))

            # Sort sections based on index and add to Subject
            sections_list.sort(key=operator.itemgetter(0))
            for index, section in sections_list:
                freq.append(section.number_of_questions)
                num_circle.append(section.number_of_options)
                subject.add_section(section)

    print(freq, num_circle)
    time_end = time.time()
    print("time taken to get data from database", time_end - time_start)
    time_start = time.time()

    resize_a = image.width
    resize_b = image.height
    coordinates = [
        (
            (0 / 2480) * resize_a,
            (0 / 3508) * resize_b,
            (700 / 2480) * resize_a,
            (3500 / 3508) * image.height,
        ),
        (
            ((660) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((1280) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
        (
            ((1260) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((1870) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
        (
            ((1800) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((2450) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
    ]

    img1, img2, img3, img4 = [image.crop(coord) for coord in coordinates]
    images_path = [img1, img2, img3, img4]

    img = merge_images(images_path)
    img.save("merged.png")

    image = cv2.imread(
        f"merged.png",
        cv2.IMREAD_GRAYSCALE,
    )
    # image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # from here on add the code to retrive the answerkey that was stored in the exam document of that name and then also make sure you do the comparison and then store the results in the results section

    # equalized_image = cv2.equalizeHist(image)
    img = image
    
    img = np.array(img)
    time_end = time.time()
    print("time taken to create image in readable format", time_end - time_start)
    time_start = time.time()
    binary_string = ""
    counter = 0
    gray = cv2.medianBlur(img, 5)
    gray = np.uint8(gray)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        1,
        (55 * resize_a) / 2480,
        param1=20,
        param2=13,
        minRadius=int((20 * resize_a) / 2480),
        maxRadius=int((30 * resize_a) / 2480),
        
    )
    number = 0
    # time_start = time.time()
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        circles = sorted(circles, key=lambda circle: circle[1])
        sorted_circles = []
        total_circle = 0
        for index1, index2 in zip(freq, num_circle):
            for i in range(total_circle, index1 * index2 + total_circle, index2):
                sorted_group = sorted(
                    circles[i : i + index2], key=lambda circle: circle[0]
                )
                sorted_circles.extend(sorted_group)
            total_circle += index1 * index2
        
        roll_number = 0
        count = 0
        count2 = 0
        final_list = []
        
        for i, j in zip(freq, num_circle):
            for k in range(i):
                final_list.append(j)
        flag  = False
        set_string = ""
        set_number = 1
        set_count = 0
        for x, y, r in sorted_circles:
            if(set_count == 3 and flag):
                flag = False
                binary_string = ""
                if(set_string  == "100"):
                    set_number = 1
                if set_string == "010":
                    set_number = 2
                if set_string == "001":
                    set_number = 3

                print(set_number)
                
            count += 1
            mask = np.zeros_like(gray)
            cv2.circle(mask, (x, y), r, (255), -1)
            black_pixels = np.sum((mask == 255) & (gray <= 120))
            total_pixels = np.sum(mask == 255)
            black_proportion = black_pixels / total_pixels
            if black_proportion > 0.2:
                cv2.circle(img, (x, y), r, (0, 0, 255), -1)
                cv2.circle(img, (x, y), r, (0, 255, 0), 4)
                binary_string += "1"
                if(flag):
                    set_string += "1"
                    set_count+=1
                # file.write("1 ")
                print("1",end=" ")
            else:
                cv2.circle(img, (x, y), r, (0, 255, 0), 4)
                binary_string += "0"
                if(flag):
                    set_string += "0"
                    set_count+=1
                # file.write("0 ")
                print("0",end=" ")
            if count == final_list[count2]:
                count = 0
                count2 += 1
                print()
                # file.write("\n")
                roll_number += 1
                if roll_number == 10:
                    roll = binary_string
                    binary_string = ""
                    roll_number_string = extract_roll(roll)
                    roll_number_student  = int(roll_number_string)
                    print(roll_number_string,end=" ")
                    flag = True
                # print(1)
        output = (
            "test"
            + str(0)
            + ".png"
        )
        cv2.imwrite(output, img)
        # print(bianry_string)
    else:
        print("No circles were found")
    time_end = time.time()
    print("time taken to create binary string of answers: ", time_end - time_start)
    time_start = time.time()
    query_results = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
    documents = query_results.get()
    for document in documents:
        print(document.to_dict())
        # answer_key = document.get("Answer_key_1")

    # answer_key_exam = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam).get()
    answer_key = ""
    if( set_number  == 1):
        answer_key = documents[0].get("Answer_Key_1")
    if( set_number  == 2):
        answer_key = documents[0].get("Answer_Key_2")
    if( set_number  == 3):
        answer_key = documents[0].get("Answer_Key_3")

    correct_marks = 2
    incorrect_marks = 1

    marks = 0

    for i in range(len(answer_key)):
        if answer_key[i] == binary_string[i]:
            marks += correct_marks
        else:
            marks -= incorrect_marks
            
    results_ref.add(
        {
            "Roll_Number": str(roll_number_student),
            "Exam_Name": name_of_exam,
            "Admin_Email":  admin_email,
            "Marks": str(0),
        }
    )
    print("total time", time_end - tt)
    return jsonify({"message": "Image received successfully"}), 200
    # else:
    #     return jsonify({"message": "Image not received successfully"}), 400

@app.route("/receive_answser_key", methods=["POST"])
def receive_answer_key():
    print("answer key received")
    tt = time.time()
    time_start = time.time()
    results_ref = db.collection("Results")
    if "image" not in request.files:
        return jsonify({"message": "No image in request"}), 400
    viewfinder_image = request.files["image"]

    name_of_exam = request.form["examName"]
    admin_email = request.form["adminEmail"]
    image = Image.open(BytesIO(viewfinder_image.read()))

    # print(name_of_exam, admin_email)
    # viewfinder_image_path = (
    #     "testing_scan.jpg"
    # )#change this file to the one that is received from the app
    # viewfinder_image.save(viewfinder_image_path)
    # image = Image.open(viewfinder_image_path)


    # response_from_orientation = give_correct_image_orientation(image)
    time_end = time.time()
    print("time taken to get image from app", time_end - time_start)
    time_start = time.time()
    print(name_of_exam, admin_email)
    freq = []
    num_circle = []

    # Get Exam data from Firestore
    exams_ref = db.collection('Exams')
    query_ref = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
    exams_docs = query_ref.stream()

    for exam_doc in exams_docs:
        exam_data = exam_doc.to_dict()

        # Create OMR object
        roll_number_digits = exam_data.get('Roll_Number_Digits', None)
        exam_sets = exam_data.get('Exam_Sets', None)
        num_subjects = exam_data.get('Number_of_Subjects', None)
        omr = OMR(roll_number_digits, exam_sets, num_subjects)
        freq.append(10)
        freq.append(1)
        num_circle.append(5)
        num_circle.append(3)
        # Get Subjects data from Firestore
        subjects_ref = db.collection('Subjects')
        query_ref = subjects_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
        subjects_docs = query_ref.stream()

        # Store all subjects in a list
        subjects_list = []
        for subject_doc in subjects_docs:
            subject_data = subject_doc.to_dict()
            num_sections = subject_data.get('Number_of_Sections', None)
            subject_name = subject_data.get('Subject_Name', None)
            subject = Subject(subject_name, num_sections)
            subjects_list.append((subject_data['index'], subject))

        # Sort subjects based on index and add to OMR
        subjects_list.sort(key=operator.itemgetter(0))
        for index, subject in subjects_list:
            omr.add_subject(subject)

            # Get Sections data from Firestore
            sections_ref = db.collection('Sections')
            query_ref = sections_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam).where('Subject_Name', '==', subject.name)
            sections_docs = query_ref.stream()

            # Store all sections in a list
            sections_list = []
            for section_doc in sections_docs:
                section_data = section_doc.to_dict()
                num_questions = section_data.get('Questions', None)
                num_options = section_data.get('Options', None)
                question_type = section_data.get('Question_Type', None)
                section_heading = section_data.get('Section_Heading', None)
                section = Section(num_questions, num_options, question_type, section_heading, 0)
                sections_list.append((section_data['index'], section))

            # Sort sections based on index and add to Subject
            sections_list.sort(key=operator.itemgetter(0))
            for index, section in sections_list:
                freq.append(section.number_of_questions)
                num_circle.append(section.number_of_options)
                subject.add_section(section)

    print(freq, num_circle)
    time_end = time.time()
    print("time taken to get data from database", time_end - time_start)
    time_start = time.time()

    resize_a = image.width
    resize_b = image.height
    coordinates = [
        (
            (0 / 2480) * resize_a,
            (0 / 3508) * resize_b,
            (700 / 2480) * resize_a,
            (3500 / 3508) * image.height,
        ),
        (
            ((660) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((1280) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
        (
            ((1260) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((1870) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
        (
            ((1800) / 2480) * resize_a,
            (0 / 3508) * resize_b,
            ((2450) / 2480) * resize_a,
            (3500 / 3508) * resize_b,
        ),
    ]

    img1, img2, img3, img4 = [image.crop(coord) for coord in coordinates]
    images_path = [img1, img2, img3, img4]

    img = merge_images(images_path)
    img.save("merged.png")

    image = cv2.imread(
        f"merged.png",
        cv2.IMREAD_GRAYSCALE,
    )
    # image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # from here on add the code to retrive the answerkey that was stored in the exam document of that name and then also make sure you do the comparison and then store the results in the results section

    # equalized_image = cv2.equalizeHist(image)
    img = image
    
    img = np.array(img)
    time_end = time.time()
    print("time taken to create image in readable format", time_end - time_start)
    time_start = time.time()
    binary_string = ""
    counter = 0
    gray = cv2.medianBlur(img, 5)
    gray = np.uint8(gray)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        1,
        (55 * resize_a) / 2480,
        param1=20,
        param2=13,
        minRadius=int((20 * resize_a) / 2480),
        maxRadius=int((30 * resize_a) / 2480),
        
    )
    number = 0
    # time_start = time.time()
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        circles = sorted(circles, key=lambda circle: circle[1])
        sorted_circles = []
        total_circle = 0
        for index1, index2 in zip(freq, num_circle):
            for i in range(total_circle, index1 * index2 + total_circle, index2):
                sorted_group = sorted(
                    circles[i : i + index2], key=lambda circle: circle[0]
                )
                sorted_circles.extend(sorted_group)
            total_circle += index1 * index2
        
        roll_number = 0
        count = 0
        count2 = 0
        final_list = []
        
        for i, j in zip(freq, num_circle):
            for k in range(i):
                final_list.append(j)
        flag  = False
        set_string = ""
        set_number = 1
        set_count = 0
        for x, y, r in sorted_circles:
            if(set_count == 3 and flag):
                flag = False
                binary_string = ""
                if(set_string  == "100"):
                    set_number = 1
                if set_string == "010":
                    set_number = 2
                if set_string == "001":
                    set_number = 3

                print(set_number)
                
            count += 1
            mask = np.zeros_like(gray)
            cv2.circle(mask, (x, y), r, (255), -1)
            black_pixels = np.sum((mask == 255) & (gray <= 120))
            total_pixels = np.sum(mask == 255)
            black_proportion = black_pixels / total_pixels
            if black_proportion > 0.2:
                cv2.circle(img, (x, y), r, (0, 0, 255), -1)
                cv2.circle(img, (x, y), r, (0, 255, 0), 4)
                binary_string += "1"
                if(flag):
                    set_string += "1"
                    set_count+=1
                # file.write("1 ")
                print("1",end=" ")
            else:
                cv2.circle(img, (x, y), r, (0, 255, 0), 4)
                binary_string += "0"
                if(flag):
                    set_string += "0"
                    set_count+=1
                # file.write("0 ")
                print("0",end=" ")
            if count == final_list[count2]:
                count = 0
                count2 += 1
                print()
                # file.write("\n")
                roll_number += 1
                if roll_number == 10:
                    roll = binary_string
                    binary_string = ""
                    roll_number_string = extract_roll(roll)
                    roll_number_student  = int(roll_number_string)
                    print(roll_number_string,end=" ")
                    flag = True
                # print(1)
        output = (
            "test"
            + str(0)
            + ".png"
        )
        cv2.imwrite(output, img)
        # print(bianry_string)
    else:
        print("No circles were found")
    time_end = time.time()
    print("time taken to create binary string of answers: ", time_end - time_start)
    time_start = time.time()

    
    query_results = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)

# Get the documents from the query
    documents = query_results.get()

    field_name = ""
    if set_number == 1:
        field_name = "Answer_Key_1"
    if set_number == 2:
        field_name = "Answer_Key_2"
    if set_number == 3:
        field_name = "Answer_Key_3"
    for document in documents:
    # Update each document
        document.reference.update({field_name: binary_string})


    marks = 0
    print("total time", time_end - tt)
    return jsonify({"message": "Image received successfully"}), 200

def delete_from_db(request_data):
    admin_email = request_data.get("Admin_Email")
    exam_name = request_data.get("Exam_Name")
    collections = ["Exams", "Sections", "Subjects"]
    for collection_name in collections:
        # Create a reference to the collection
        collection_ref = db.collection(collection_name)

        # Create a query to filter documents based on the field value
        query = collection_ref.where("Admin_Email", "==", admin_email).where(
            "Exam_Name", "==", exam_name
        )
        docs = query.stream()

        # Iterate through the documents and delete them
        for doc in docs:
            doc.reference.delete()
            print(f"Deleted document with ID: {doc.id}")
    return

@app.route("/delete_exam", methods=["POST"])
def delete_exam():
    data = request.get_json()
    print(data)

    admin_email = data.get("Admin_Email")
    exam_name = data.get("Exam_Name")

    if not admin_email or not exam_name:
        return {"error": "Admin_Email or Exam_Name missing in the request"}, 400
    thread = threading.Thread(target=delete_from_db, args=(data,))
    thread.start()
    return {"status": "Deleted successfully"}, 200

import operator

def delete_exam():
    

    admin_email = input()
    exam_name = input()

    if not admin_email or not exam_name:
        return {"error": "Admin_Email or Exam_Name missing in the request"}, 400

    # Collections you want to delete from
    collections = ['Exams', 'Sections', 'Subjects']

    for collection_name in collections:
    # Create a reference to the collection
        collection_ref = db.collection(collection_name)

        # Create a query to filter documents based on the field value
        query = collection_ref.where("Admin_Email", '==', admin_email).where("Exam_Name", '==', exam_name)
        docs = query.stream()

        # Iterate through the documents and delete them
        for doc in docs:
            doc.reference.delete()
            print(f"Deleted document with ID: {doc.id}")


def print_freq(name_of_exam, admin_email):
    print(name_of_exam, admin_email)

    freq = []
    num_circle = []

    # Get Exam data from Firestore
    exams_ref = db.collection('Exams')
    query_ref = exams_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
    exams_docs = query_ref.stream()

    for exam_doc in exams_docs:
        exam_data = exam_doc.to_dict()

        # Create OMR object
        roll_number_digits = exam_data.get('Roll_Number_Digits', None)
        exam_sets = exam_data.get('Exam_Sets', None)
        num_subjects = exam_data.get('Number_of_Subjects', None)
        omr = OMR(roll_number_digits, exam_sets, num_subjects)
        freq.append(10)
        freq.append(1)
        num_circle.append(5)
        num_circle.append(3)
        # Get Subjects data from Firestore
        subjects_ref = db.collection('Subjects')
        query_ref = subjects_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam)
        subjects_docs = query_ref.stream()

        # Store all subjects in a list
        subjects_list = []
        for subject_doc in subjects_docs:
            subject_data = subject_doc.to_dict()
            num_sections = subject_data.get('Number_of_Sections', None)
            subject_name = subject_data.get('Subject_Name', None)
            subject = Subject(subject_name, num_sections)
            subjects_list.append((subject_data['index'], subject))

        # Sort subjects based on index and add to OMR
        subjects_list.sort(key=operator.itemgetter(0))
        for index, subject in subjects_list:
            omr.add_subject(subject)

            # Get Sections data from Firestore
            sections_ref = db.collection('Sections')
            query_ref = sections_ref.where('Admin_Email', '==', admin_email).where('Exam_Name', '==', name_of_exam).where('Subject_Name', '==', subject.name)
            sections_docs = query_ref.stream()

            # Store all sections in a list
            sections_list = []
            for section_doc in sections_docs:
                section_data = section_doc.to_dict()
                num_questions = section_data.get('Questions', None)
                num_options = section_data.get('Options', None)
                question_type = section_data.get('Question_Type', None)
                section_heading = section_data.get('Section_Heading', None)
                section = Section(num_questions, num_options, question_type, section_heading, 0)
                sections_list.append((section_data['index'], section))

            # Sort sections based on index and add to Subject
            sections_list.sort(key=operator.itemgetter(0))
            for index, section in sections_list:
                freq.append(section.number_of_questions)
                num_circle.append(section.number_of_options)
                subject.add_section(section)

    print(freq, num_circle)


if __name__ == "__main__":
    app.run(host="0.0.0.0")
    # name = input()
    # name2 = input()
    # delete_exam()
    


