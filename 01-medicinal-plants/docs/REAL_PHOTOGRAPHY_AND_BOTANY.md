# Real photograph and botany provenance

This project **does not** use AI-generated plant illustrations, synthetic plant photos, Pinterest-rehosted images or photographs of a different species. The logo is a vector graphic; the botanical catalog uses image URLs from species-labelled Wikimedia Commons photographs.

The photos are species reference images, **not photographs of the live plant a seller will ship**. A seller should later upload its own photographed inventory. The photos currently load over the internet. To build a local offline image cache, on an internet-connected computer run `python scripts/cache_commons_photos.py`. The cache script did not run successfully in the model's restricted environment, so **the ZIP does not contain the photographs themselves**. If images are blocked, the UI supplies a text and source-link fallback instead of a fake illustration.

## Sources, photographers and licenses

| Product | Wikimedia Commons original file (source/credit) | Photographer / uploader | License | Scientific identity |
|---|---|---|---|---|
| Tulsi | https://commons.wikimedia.org/wiki/File:Ocimum_tenuiflorum_plant.jpg | Krisnendu Paul | CC BY-SA 4.0 | https://powo.science.kew.org/taxon/453130-1 |
| Neem | https://commons.wikimedia.org/wiki/File:Azadirachta_indica,_Neem.jpg | Varinder Naturaphile | CC BY-SA 4.0 | https://powo.science.kew.org/taxon/1213180-2 |
| Aloe vera | https://commons.wikimedia.org/wiki/File:Aloe_Vera_growing_plant.jpg | Agambire Sylvanus | CC0 1.0 | https://powo.science.kew.org/taxon/530017-1 |
| Ashwagandha | https://commons.wikimedia.org/wiki/File:An_image_of_Withania_somnifera.JPG | Thamizhpparithi Maari | CC BY-SA 3.0 | https://powo.science.kew.org/taxon/821709-1 |
| Brahmi | https://commons.wikimedia.org/wiki/File:Bacopa_monnieri.jpg | Vinayaraj | CC BY-SA 3.0 | https://powo.science.kew.org/taxon/1072674-2 |
| Amla | https://commons.wikimedia.org/wiki/File:Phyllanthus_emblica_(Indian_Gooseberry).jpg | Haneeshkm | CC BY-SA 4.0 | https://powo.science.kew.org/taxon/353838-1 |
| Lemongrass | https://commons.wikimedia.org/wiki/File:Cymbopogon_citratus.jpg | Nativeplants garden | CC BY-SA 4.0 | https://powo.science.kew.org/taxon/396896-1 |
| Mint | https://commons.wikimedia.org/wiki/File:Mentha_spicata.jpg | Schumi4ever | CC BY-SA 4.0 | https://powo.science.kew.org/taxon/451162-1 |

License URLs:
- https://creativecommons.org/licenses/by-sa/4.0/
- https://creativecommons.org/licenses/by-sa/3.0/
- https://creativecommons.org/publicdomain/zero/1.0/

Attribution and license links are rendered in each product card and photo detail. The site should also retain license notices, links, and change notices if images are modified, and meet all image-specific requirements before commercial launch. Linked source-file names are grounded in Wikimedia Commons pages, but the original images were not downloaded or independently visually inspected inside this environment.

**Important identification note:** Source-file labels can be mistaken. Before accepting vendor inventory as authentic, have a trained botanist or credible nursery verify the exact species and variant. A stock photograph is not an identity certificate.

## Botanical description methodology

Each product has a `fact_sheet` in `server/app.py`, together with taxonomic records from Kew Plants of the World Online. The fact sheet describes morphology, broad distribution, cultural history, common use and clear evidence boundaries. Scientific names may change with later taxonomic revision.

Medicinal folklore, herbal preparations and clinical efficacy are distinct. No product is represented as curing an illness, replacing a prescribed medicine or being safe for everyone. Commercial distribution of plants/medicines would require local business, plant quarantine, wildlife, labelling, packaging and relevant regulatory review.

## Visual direction

This is an original **dark botanical commerce system**, not a copy of Pinterest UI: forest charcoal background, moss-green surfaces, warm stone text, aged brass CTA buttons and copper/amber visual accents. Original vector monogram, hover motion, staggered product reveal, image zoom, animated route/orbit detail, slide-in drawers, keyboard search shortcut and reduced-motion accessibility are implemented. The catalog begins directly after a compact commerce collection feature, not a long landing-page narrative.
