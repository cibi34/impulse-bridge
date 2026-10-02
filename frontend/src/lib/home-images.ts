/**
 * Artworks shown on the home page. Each file is a public-domain work, marked
 * "Public domain" (not copyrighted) on Wikimedia Commons, and served from
 * this server (static/home/). They are credited on the Credits page.
 */
export interface HomeImage {
	file: string;
	title: string;
	artist: string;
	commons: string;
}

export const homeImages = {
	vermeer: {
		file: 'home/vermeer.webp',
		title: 'Girl with a Pearl Earring',
		artist: 'Johannes Vermeer',
		commons: 'https://commons.wikimedia.org/wiki/File:1665_Girl_with_a_Pearl_Earring.jpg'
	},
	hokusai: {
		file: 'home/hokusai.webp',
		title: 'The Great Wave off Kanagawa',
		artist: 'After Katsushika Hokusai',
		commons: 'https://commons.wikimedia.org/wiki/File:Great_Wave_off_Kanagawa2.jpg'
	},
	durer: {
		file: 'home/durer.webp',
		title: 'Young Hare',
		artist: 'Albrecht Dürer',
		commons: 'https://commons.wikimedia.org/wiki/File:A_Young_Hare,_Albrect_Durer.jpg'
	},
	monet: {
		file: 'home/monet.webp',
		title: 'Water-Lily Pond and Weeping Willow',
		artist: 'Claude Monet',
		commons:
			'https://commons.wikimedia.org/wiki/File:Claude_Monet,_Water-Lily_Pond_and_Weeping_Willow.JPG'
	},
	vangogh: {
		file: 'home/vangogh.webp',
		title: 'The Starry Night',
		artist: 'Vincent van Gogh',
		commons: 'https://commons.wikimedia.org/wiki/File:VanGogh-starry_night_ballance1.jpg'
	},
	klimt: {
		file: 'home/klimt.webp',
		title: 'The Kiss (detail)',
		artist: 'Gustav Klimt',
		commons: 'https://commons.wikimedia.org/wiki/File:Klimt_-_The_Kiss_(detail).jpg'
	},
	botticelli: {
		file: 'home/botticelli.webp',
		title: 'The Birth of Venus',
		artist: 'Sandro Botticelli',
		commons: 'https://commons.wikimedia.org/wiki/File:La_nascita_di_Venere_(Botticelli).jpg'
	}
} as const satisfies Record<string, HomeImage>;
