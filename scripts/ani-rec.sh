curl -X POST https://graphql.anilist.co \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -d '{
    "query": "query ($userName: String) { MediaListCollection(userName: $userName, type: ANIME, status: COMPLETED, sort: SCORE_DESC) { lists { entries { score media { title { english romaji } recommendations(sort: RATING_DESC, perPage: 3) { nodes { mediaRecommendation { title { english romaji } seasonYear format } } } } } } } }",
    "variables": {
      "userName": "cmaguranis"
    }
  }' | jq -r '
  ["Source Anime", "Your Score", "Recommended Anime", "Year", "Format"],
  (
    .data.MediaListCollection.lists[]?.entries[]?
    | (.media.title.english // .media.title.romaji) as $source
    | .score as $score
    | .media.recommendations.nodes[]?.mediaRecommendation
    | select(. != null)
    | [
        $source,
        ($score | tostring),
        (.title.english // .title.romaji),
        (.seasonYear | tostring),
        .format
      ]
  ) | @tsv
' | column -t -s $'\t'