"""One answer to 'is this shopper a man or a woman' that every voice picker uses: explicit persona.gender, else the female/male voice
label, else the first name, else pronouns in the summary. 'young' and 'older' are AGE labels and never decide gender."""
import re
from typing import Optional

MALE = set("""aaron adam adrian al alan albert alex alexander alfred allen andre andrew andy angel anthony antonio arthur austin barry ben benjamin bernard bill billy blake bob bobby brad bradley brandon brent brett brian bruce bryan
caleb calvin cameron carl carlos casey cesar chad charles charlie chase chris christian christopher chuck clarence clayton clifford clint clyde cody colin connor corey craig curtis dale dan daniel danny darrell darren darryl dave david dean dennis derek derrick devin dewey dominic don donald doug douglas drew duane dustin dwayne dwight
earl ed eddie edgar eduardo edward edwin eli elijah elliot eric erik ernest ethan eugene evan everett felix fernando floyd francis francisco frank franklin fred freddie frederick gabriel garrett gary gene geoffrey george gerald gilbert glen glenn gordon grant greg gregory guy
hank harold harry harvey hector henry herbert herman howard hugh hunter ian isaac ivan jack jackson jacob jake jamal james jared jason javier jay jeff jeffrey jeremiah jeremy jerome jerry jesse jesus jim jimmy joe joel joey john johnny jon jonathan jordan jorge jose joseph josh joshua juan julian julio justin
keith kelvin ken kenneth kenny kent kevin kirk kurt kyle lance larry lawrence lee leo leon leonard leroy leslie lester lewis lloyd logan lonnie louis lucas luis luke manuel marc marcus mario mark marshall martin marvin mason matt matthew maurice max melvin michael miguel mike milton mitchell morris nate nathan nathaniel neil nelson nicholas nick noah norman
oliver omar oscar owen patrick paul pedro percy perry pete peter phil philip phillip preston rafael ralph ramon randall randy ray raymond reginald rene rex ricardo richard rick ricky rob robert roberto rodney roger roland ron ronald ronnie ross roy ruben russell ryan
sam samuel scott sean sergio seth shane shawn sidney spencer stan stanley stephen steve steven stuart ted terrence terry theodore thomas tim timothy todd tom tommy tony travis trevor troy tyler tyrone vernon victor vincent virgil wade wallace walt walter warren wayne wes wesley willard william willie wyatt zachary
piet kees henk johan willem hans jeroen bas sander bram daan lars maarten mark martijn niels pieter rob ruud stefan sven thijs thomas tim tom wouter""".split())
FEMALE = set("""abby abigail ada adriana agnes aimee alexa alexandra alexis alice alicia alison allison alma alyssa amanda amber amy ana andrea angela angie anita ann anna anne annette annie april ariana ashley audrey autumn ava barbara beatrice becky belinda bernice bertha beth bethany betty beverly bonnie brandi brenda briana bridget brittany brooke
caitlin camille candace candice carla carmen carol carole caroline carolyn carrie cassandra catherine cathy cecilia celeste charlene charlotte chelsea cheryl chloe christina christine christy cindy claire clara claudia colleen connie constance courtney crystal cynthia daisy dana danielle darlene dawn deanna debbie deborah debra delores denise desiree diana diane dianne dolores donna dora doris dorothy
edith edna eileen elaine eleanor elena elizabeth ella ellen elsie emily emma erica erin esther ethel eva evelyn faith faye felicia florence frances gabriela gail gina gladys glenda gloria grace gretchen gwen hannah harriet hazel heather heidi helen hilda holly ida irene iris irma isabel isabella jackie jacqueline jamie jane janet janice jasmine jean jeanette jeanne jenna jennifer jenny jessica jill jo joan joann joanna joanne jodi jody josephine joy joyce judith judy julia julie june
kara karen kari karla kate katherine kathleen kathryn kathy katie katrina kay kayla kelly kendra kerry kim kimberly kirsten krista kristen kristi kristin kristina kristine krystal lauren laura laurie leah lena leslie lillian linda lindsay lindsey lisa lois loretta lori lorraine louise lucille lucy lydia lynn mabel madison mae maggie mallory mandy marcia margaret margie maria marian marie marilyn marion marjorie marlene marsha martha mary maureen maya megan melanie melinda melissa melody meredith michele michelle mildred minnie miriam misty molly monica monique myra myrtle
nancy naomi natalie natasha nichole nicole nina nora norma olga olivia pam pamela pat patricia patsy patty paula pauline peggy penny phyllis priscilla priya rachel ramona rebecca regina renee rhonda rita roberta robin robyn rochelle rosa rose rosemary ruby ruth sabrina sally samantha sandra sandy sara sarah shannon sharon sheila shelby shelley shelly sheri sherri sherry shirley sonia sonya sophia stacey stacy stella stephanie sue susan suzanne sylvia
tamara tami tammy tanya tara tasha teresa terri theresa tiffany tina toni tonya tracey tracy tricia valerie vanessa velma vera veronica vicki vickie vicky victoria viola violet virginia vivian wanda wendy whitney wilma yolanda yvonne zoe
anke anna anouk annemarie carla daniëlle danielle els emma esther eva femke fleur floor hanna ilse iris janneke joke josé judith karin kim laura linda lisa lotte maaike marieke marjolein monique nienke petra renate sanne saskia sophie suzanne tessa wendy yvonne""".split())
UNISEX = set("sam alex casey jamie jordan taylor morgan riley drew jesse leslie kelly kim robin lee dana chris pat terry tracy shannon jody jodi kerry avery quinn skyler dakota devon jean francis frankie".split())
MALE |= UNISEX
FEMALE |= UNISEX  # in both sets = ambiguous = the label decides
_HE = re.compile(r"\b(he|him|his|himself|man|guy|husband|father|dad|grandfather|retired engineer)\b", re.I)
_SHE = re.compile(r"\b(she|her|hers|herself|woman|lady|wife|mother|mom|grandmother)\b", re.I)


def first_name_gender(name: Optional[str]) -> Optional[str]:
    first = re.sub(r"[^a-zA-Zëéï'-]", "", (name or "").strip().split(" ")[0]).lower()
    if not first:
        return None
    if first in MALE and first not in FEMALE:
        return "male"
    if first in FEMALE and first not in MALE:
        return "female"
    return None


def gender_of(persona: Optional[dict]) -> str:
    """'male' or 'female'. Order: explicit gender, an unambiguous first name, a female/male voice label, pronouns in the text, then female."""
    p = persona or {}
    g = str(p.get("gender") or "").lower()
    if g in ("male", "female"):
        return g
    by_name = first_name_gender(p.get("name"))  # an unambiguous first name beats a slipped label (the Bill-with-a-woman's-voice bug)
    if by_name:
        return by_name
    v = str(p.get("voice") or "").lower()
    if v in ("male", "female"):
        return v
    text = " ".join(str(p.get(k) or "") for k in ("summary", "goals"))
    he, she = len(_HE.findall(text)), len(_SHE.findall(text))
    if he != she:
        return "male" if he > she else "female"
    return "female"


def age_of(persona: Optional[dict]) -> Optional[str]:
    """'young' / 'older' from the voice label or the age in the summary, else None."""
    p = persona or {}
    v = str(p.get("voice") or "").lower()
    if v in ("young", "older"):
        return v
    m = re.match(r"\s*(\d{2})\b", str(p.get("summary") or ""))
    if m:
        age = int(m.group(1))
        return "young" if age <= 29 else "older" if age >= 55 else None
    return None


def describe(persona: Optional[dict]) -> str:
    """'a man in his 60s' style phrase for prompts, so the model's manner matches the voice it was given."""
    g = "man" if gender_of(persona) == "male" else "woman"
    a = age_of(persona)
    return f"{'an older' if a == 'older' else 'a young' if a == 'young' else 'a'} {g}"


def voice_label(persona: Optional[dict]) -> str:
    """The legacy 4-way label with gender made explicit: young/older stay for women (the relay voices have those), men are always 'male'."""
    g = gender_of(persona)
    if g == "male":
        return "male"
    a = age_of(persona)
    return a if a in ("young", "older") else "female"
