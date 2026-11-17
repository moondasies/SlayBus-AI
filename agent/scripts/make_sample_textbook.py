"""Create a small sample science textbook PDF for testing and demos.

Usage:
    python scripts/make_sample_textbook.py out.pdf              # with PDF bookmarks
    python scripts/make_sample_textbook.py out.pdf --no-toc     # headings only

The text is original, written for SLAYBUS testing (Class 7 level).
"""

from __future__ import annotations

import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

CHAPTERS = [
    ("Nutrition in Plants", [
        "All living organisms need food. Food gives them the energy to grow, move and repair their bodies. "
        "Plants are the only organisms that can make their own food from simple substances. For this reason plants "
        "are called autotrophs. Animals, including humans, depend on plants directly or indirectly for food, so they "
        "are called heterotrophs.",
        "The process by which green plants make their own food is called photosynthesis. During photosynthesis, "
        "plants use carbon dioxide from the air and water from the soil. In the presence of sunlight and chlorophyll, "
        "these are converted into carbohydrates such as glucose. Oxygen is released as a by-product of photosynthesis.",
        "Leaves are known as the food factories of plants. The green colour of leaves comes from a pigment called "
        "chlorophyll, which traps the energy of sunlight. The surface of a leaf has tiny pores called stomata. "
        "Carbon dioxide enters the leaf through the stomata, and oxygen and water vapour leave through them. Each "
        "stoma is surrounded by a pair of guard cells that open and close the pore.",
        "Water and minerals are absorbed from the soil by the roots. They are carried to the leaves through "
        "vessels in the stem. The carbohydrates made in the leaves are first stored as starch. The presence of "
        "starch in a leaf can be tested with iodine solution, which turns blue-black in the presence of starch.",
        "Some plants do not have chlorophyll and cannot make their own food. Cuscuta, also called Amarbel, is a "
        "parasite that wraps around a host plant and takes ready-made food from it. A plant that lives on another "
        "organism and takes food from it is called a parasite, and the organism it feeds on is called the host.",
        "Insectivorous plants, such as the pitcher plant, trap and digest insects. The leaf of the pitcher plant is "
        "modified into a pitcher-like structure with a lid. Insects that enter the pitcher get trapped in the hair "
        "inside and are digested by juices secreted in the pitcher. These plants grow in soil that is poor in "
        "nitrogen, so insects provide the nitrogen they need.",
        "Some organisms take their nutrients from dead and decaying matter. This mode of nutrition is called "
        "saprotrophic nutrition, and the organisms are called saprotrophs. Fungi such as mushrooms and bread mould "
        "are common saprotrophs. They release digestive juices onto dead matter and absorb the dissolved nutrients.",
        "Some organisms live together and share shelter and nutrients. This relationship is called symbiosis. A "
        "lichen is a partnership between an alga and a fungus. The alga contains chlorophyll and makes food, while "
        "the fungus provides shelter, water and minerals. Bacteria called Rhizobium live in the root nodules of "
        "leguminous plants such as gram and peas. They convert nitrogen from the air into a form the plant can use.",
        "Soil loses its nutrients as crops grow on it. Farmers add manures and fertilisers to the soil to replace "
        "nutrients such as nitrogen, phosphorus and potassium. Growing leguminous crops in rotation with other crops "
        "naturally adds nitrogen back to the soil.",
    ]),
    ("Heat", [
        "We use the words hot and cold to describe how warm an object is. A reliable measure of the hotness of an "
        "object is its temperature. Temperature is measured with a device called a thermometer. The unit of "
        "temperature commonly used in our country is the degree Celsius, written as °C.",
        "A clinical thermometer is used to measure the temperature of the human body. It has a long, narrow glass "
        "tube with a bulb at one end containing mercury. Its range is from 35 °C to 42 °C. The normal temperature of "
        "the human body is about 37 °C. A clinical thermometer has a kink that stops the mercury level from falling "
        "on its own, so the reading can be noted after it is taken out of the mouth.",
        "A laboratory thermometer is used to measure the temperature of other objects. Its range is usually from "
        "-10 °C to 110 °C. While using it, the thermometer should be kept upright and the bulb should be surrounded "
        "by the substance whose temperature is being measured. The bulb should not touch the bottom or sides of the "
        "container.",
        "Heat flows from a hotter object to a colder object. There are three ways in which heat is transferred: "
        "conduction, convection and radiation. The process by which heat is transferred from the hotter end of an "
        "object to its colder end is called conduction. In solids, heat is generally transferred by conduction.",
        "Materials that allow heat to pass through them easily are called conductors of heat. Metals such as "
        "aluminium, iron and copper are good conductors. Materials that do not allow heat to pass through them "
        "easily are called poor conductors or insulators. Plastic, wood, air and water are poor conductors of heat. "
        "This is why cooking pans have plastic or wooden handles.",
        "In liquids and gases, heat is transferred mainly by convection. When water is heated, the water near the "
        "flame gets hot and rises. Colder water from the sides moves down towards the source of heat. This "
        "movement continues until the whole of the water gets heated. The same process causes sea breeze and land "
        "breeze in coastal areas. During the day the land heats faster than the water, so cool air from the sea "
        "moves towards the land; this is called a sea breeze. At night the land cools faster, so air moves from the "
        "land to the sea; this is called a land breeze.",
        "Heat from the Sun reaches us by radiation. Radiation does not need any medium; it can take place even "
        "through a vacuum. All hot bodies radiate heat. When this heat falls on an object, part of it is reflected, "
        "part of it is absorbed and part of it may be transmitted.",
        "Dark-coloured objects absorb more heat than light-coloured objects. That is why we feel more comfortable in "
        "light-coloured clothes in summer, and prefer dark-coloured clothes in winter. Woollen clothes keep us warm "
        "because wool is a poor conductor of heat and has air trapped between its fibres, which stops heat from "
        "our body flowing out to the cold surroundings.",
    ]),
    ("Water: A Precious Resource", [
        "Water is essential for all forms of life. About 71 per cent of the surface of the Earth is covered with "
        "water, but most of it is sea water, which is salty and not fit for drinking. Only a very small fraction of "
        "the water on Earth is fresh water that can be used by humans. The United Nations observes 22 March as World "
        "Water Day to make people aware of the need to conserve water.",
        "Water exists in three forms: solid, liquid and gas. Ice is found in glaciers and the polar regions; liquid "
        "water is found in oceans, rivers, lakes and underground; and water vapour is present in the air. Water "
        "keeps moving between these forms through the water cycle, which involves evaporation, condensation and "
        "precipitation.",
        "When rain falls, some of the water seeps into the ground. This process is called infiltration. The water "
        "found below the ground is called groundwater. The upper level of groundwater is called the water table. "
        "In many places, groundwater is stored between layers of hard rock below the water table; such a layer is "
        "called an aquifer. Water from aquifers can be pumped out using tube wells or hand pumps.",
        "The water table goes down when we take out more groundwater than is replaced by rain. Increasing population, "
        "growing industries and the use of water for agriculture are the main reasons for the depletion of "
        "groundwater. Cutting forests and covering the ground with buildings and roads reduces the seepage of "
        "rainwater into the ground.",
        "Water is not evenly distributed across the country. Some places get heavy rain while others are deserts. "
        "Shortage of water in an area for a long time, due to very little or no rainfall, is called a drought.",
        "We can save water in many ways. Rainwater harvesting is the practice of collecting rainwater and storing it "
        "for later use. In one method, rainwater from rooftops is led through pipes into a storage tank. In another "
        "method, it is allowed to flow into pits so that it can recharge the groundwater. Bawris were traditional "
        "step wells used in many parts of India to collect water.",
        "Drip irrigation is a technique of watering plants through narrow tubes that deliver water directly at the "
        "base of each plant. It reduces the wastage of water and is very useful in dry areas. At home, simple habits "
        "such as turning off the tap while brushing, fixing leaking taps and reusing water used for washing "
        "vegetables to water plants help save water.",
        "When there is not enough water, plants wilt and eventually die. Without water, plants cannot make food "
        "through photosynthesis. Every one of us must use water carefully, because water is a precious resource that "
        "is shared by all living beings.",
    ]),
]


def build(path: str, with_toc: bool = True) -> None:
    body = ParagraphStyle("b", fontName="Times-Roman", fontSize=11.5, leading=16, spaceAfter=8)
    h1 = ParagraphStyle("h1", fontName="Times-Bold", fontSize=20, leading=26, spaceAfter=12)
    kicker = ParagraphStyle("k", fontName="Times-Bold", fontSize=13, leading=16, spaceAfter=2)

    story = [Paragraph("Science Explorer", h1), Paragraph("Textbook for Class VII", body),
             Paragraph("A sample book created for testing SLAYBUS.", body), PageBreak(),
             Paragraph("Contents", h1)]
    for i, (title, _) in enumerate(CHAPTERS, 1):
        story.append(Paragraph(f"Chapter {i} &nbsp; {title}", body))
    story.append(PageBreak())

    starts: list[tuple[str, int]] = []
    for i, (title, paras) in enumerate(CHAPTERS, 1):
        story.append(Paragraph(f"Chapter {i}", kicker))
        heading = Paragraph(title, h1)
        heading._slaybus_bookmark = (f"Chapter {i}: {title}", i)
        story.append(heading)
        for p in paras:
            story.append(Paragraph(p, body))
            story.append(Spacer(1, 2 * mm))
        story.append(PageBreak())

    class Doc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            mark = getattr(flowable, "_slaybus_bookmark", None)
            if mark and with_toc:
                key = f"ch{mark[1]}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(mark[0], key, level=0)

    def footer(canvas, doc):
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, str(doc.page))
        canvas.drawString(20 * mm, A4[1] - 12 * mm, "Science Explorer - Class VII")

    Doc(path, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
        title="Science Explorer Class VII").build(story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    build(sys.argv[1], with_toc="--no-toc" not in sys.argv)
    print(f"Wrote {sys.argv[1]}")
